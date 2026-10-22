# Данные и consumers Atlas: предпочтительные решения

Статус: engineering recommendations; product execution UNRUN. Реализация только после E02 acceptance и полного affected-scope rebind. Исходные критерии не сокращаются; [общие решения](00-shared-decisions.md) предотвращают второго owner. [Нормативные уточнения](decision-clarifications.md) остаются предложениями.

<a id="UI-06"></a>

## UI-06 — Land DS16 value/uncertainty grammar

Исходная запись: [tasks.json](../tasks.json), `tasks[id=UI-06]`. Review: [root-review](root-review.md#UI-06).

### Предпочтительное решение

Extend the DS4-owned value grammar and GY-AQ1 ceiling algebra through the existing Cycle Board DTO/projection and generated client. Preserve the exact DS16 set/interval/unknown/incomparable algebra, with scalar only where its owner grammar permits; represent each as an explicit alternative with value, basis/unit, purpose, provenance, rule version, and time; keep the eight AQ1 ceiling relations distinct and derive their full current set from the canonical owner. Do not render a scalar, rank, badge, or quantity from unknown/incomparable/refusal. Prepare against the pinned contract, then claim real quantity rendering only after the accepted DS7 capstone value/basis witness exists. Reuse the closed C23 refusal path.

### Что переиспользовать

- `policy-engine/src/polisyos/runtime/http/services/cycle_board_contracts.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `cycle-board value DTOs; exact symbols rebind at P0`. Existing API owner named by UI-06; no accepted-E02 claim.
- `policy-engine/src/polisyos/runtime/http/services/cycle_board_projection.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `cycle-board projection`. Existing projection waist; preserve source authority/status/time.
- `policy-engine/apps/runtime-dashboard/src/features/runs/components/AtlasRunDeck.tsx@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `Cycle Board consumer`. Existing consumer; no local scalar interpretation.
- `policy-engine/src/polisyos/foundry/contracts/state.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `ValueOuterSet and empty placeholder constructor`. DS16 C07 records an empty blocked placeholder and no production consumer; this is not a DS7 value producer.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. After E02, rebind DS4 and GY-AQ1 canonical owner identities and enumerate all eight present ceiling relations from their owner, not a copied UI list.
2. Agree a strict versioned OpenAPI oneOf grammar and round-trip bounds, member identity, unit/basis, uncertainty, purpose, provenance, rule version, and relevant time.
3. Regenerate the one canonical client family; render sets/frontiers and distinct unknown/incomparable/refusal states in DOM and MACHINE without a nearest-neighbour status.
4. Compose with accepted actual DS7 quantity/basis output and existing C23 refusal machinery; keep real quantity landing pending until that supplier exists.

### Рассмотренные альтернативы

- **Collapse to one score, midpoint, or nearest enum** — Loses set membership, incomparability, and uncertainty; a single ranking needs existing normative authorization.
- **Hand-maintain a parallel TypeScript union or wire the empty ValueOuterSet placeholder** — Creates drift or a false producer; DS16 records the placeholder as blocked and unserved.
- **Adopt a general uncertainty-visualization package** — Graphics do not supply PolicyOS semantic contract, authority boundary, or DS7 value producer.

### Free-grow и ресурсы

- **data or config growth:** Values and members grow within DS4 grammar and owner-versioned AQ1 relations; preserve the exact eight relations.
- **extension boundary:** A member within an existing algebra is data growth. A new semantic kind or comparison rule needs owner approval, schema version, generated client, and conformance.
- **resource behavior:** Render permitted set members or an explicitly typed bounded summary with completeness; never truncate to a scalar. Capacity exhaustion becomes visible unknown/refusal.


### Миграция и восстановление

Use additive schema versioning and regenerate clients before enabling consumers. Old records retain their original status; no automatic conversion from refusal or unknown to quantity. Disable the new projection on incompatibility and preserve prior artifacts and C23 history.


### Композиция и owners

- Producer algebra and API union bind to one rule/schema version; discriminator selects a variant but does not authorize it.
- Actual DS7 artifact is required for real values; a closed label, placeholder, or fixture cannot satisfy composition.
- Missing licence, mandate, authority, unknown, incomparable, or blocking loss stays refusal/limitation at the protected band.


### Acceptance и различающие проверки

- Derive all eight current AQ1 relations from canonical owner and exercise each through producer, persisted artifact, API/client, DOM and MACHINE.
- Round-trip bounds, basis, provenance, purpose, rule version, and time; mixed unknown/incomparable values never produce readiness.
- Missing licence/mandate and C23 refusals remain non-quantity; replacing actual DS7 with placeholder fails the fresh consumer.
- Remove composition but retain schema markers: semantic witness fails.


### Входы и ответственность за их получение

- Accepted DS7 capstone quantity/basis artifact or exact P0-reconciled accepted equivalent.
- Current DS4 owner and GY-AQ1 canonical set/version.
- Actual licence, mandate, and authority evidence remain external for protected actions.


### Когда обоснованно отклониться

- Without accepted DS7 values, limit to contract/surface preparation and report real-value consumer_missing.
- If an AQ1 relation lacks an owner representation, report the missing relation and do not invent a scalar projection.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [Visualizing Uncertainty in Sets (IEEE VIS 2024 / IEEE Computer Graphics and Applications)](https://www.files.ieeevis.org/year/2024/program/paper_v-cga-10198358.html) — The paper separates uncertainty affecting set membership, set attributes, and element attributes, and distinguishes certainty, undefined uncertainty, and quantifiable uncertainty. This supports separate display treatment for known sets, uncertain membership, and quantified value. **Граница:** A conceptual framework and examples, not an evaluation of PolicyOS or an admissibility rule.
- [Approximation and Visualization of Pareto Frontier in the Framework of Classical Approach to Multi-Objective Optimization](https://drops.dagstuhl.de/entities/document/10.4230/DagSemProc.04461.8) — Interactive Decision Maps supports examining a Pareto frontier under conflicting criteria and communicating results in design-variable and objective spaces. This is a precedent for showing a frontier when criteria do not license a single rank. **Граница:** The paper addresses optimization; it does not define PolicyOS value semantics or authorize scalar aggregation.
- [OpenAPI Specification 3.1.1](https://spec.openapis.org/oas/v3.1.1.html) — Schema Objects use JSON Schema; oneOf validates exactly one listed alternative. A discriminator is a selection hint and must not change validation, and alternatives must be listed explicitly beside oneOf. **Граница:** The specification does not guarantee a configured generator emits a correct client union or that clients validate hostile runtime payloads.
- [OpenAPI Generator supported generators](https://openapi-generator.tech/docs/generators/) — The project offers multiple client generators, including TypeScript targets, so the generated client family can remain the API-to-client bridge. **Граница:** Availability does not prove oneOf fidelity for this repository's selected generator/version; actual generated output and consumer need verification.
- [Parallel Change](https://www.martinfowler.com/bliki/ParallelChange.html) — Expand/migrate/contract lets clients move incrementally before the old interface is removed; temporary dual support has coordination cost and needs a real completion point. **Граница:** The pattern does not justify permanently maintaining duplicate semantics or auto-upgrading historical authority.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="UI-07"></a>

## UI-07 — Bridge DS16 derived-data provenance through N13b

Исходная запись: [tasks.json](../tasks.json), `tasks[id=UI-07]`. Review: [root-review](root-review.md#UI-07).

### Предпочтительное решение

Bridge accepted N13b derivation through existing ArtifactRef/FileSystemCAS and governed projection. Extend the exercised DerivationRecipe/DerivationCertificate, not add a provenance service: persist exact parent refs/digests, selected view, transform/parameters, rule/schema version, tenant/use, producer/verifier provenance, output ref, and applicable epoch/currentness. Projection resolves refs and rechecks current parent heads and revocation/change state before exposing the derived view; stale artifacts stay historical but are refused until N13b replay emits a new certificate.

### Что переиспользовать

- `policy-engine/src/polisyos/core/artifacts/manifest.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `ArtifactRef`. Reuse immutable CAS references rather than copying source content or inventing another ID space.
- `policy-engine/src/polisyos/core/artifacts/store.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `FileSystemCAS`. Existing persisted content-addressed owner named by UI-07.
- `policy-engine/src/polisyos/runtime/quality/derived_observations.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `DerivationRecipe; DerivationCertificate; build_derivation_recipe`. DS16 C09 records exercised substrate but no public API bridge.
- `policy-engine/src/polisyos/runtime/http/routes/governed_projections.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `get_governed_projection`. Existing projection boundary; rebind exact route at P0.
- `policy-engine/src/polisyos/runtime/quality/acquisition_world_growth.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `world-growth and acquisition provenance owner`. Reuse current owner for parent changes and re-entry.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. After recorded exact DerivationRecipe/DerivationCertificate interface agreement, compare contracts and prepare isolated UI projection/oracles. Real accepted N13b producer, persistence, invalidation, replay/re-entry and fresh read remain composed-acceptance requirements; wait only on a named unresolved interface predicate, not the whole chain for preparation.
2. Compare DerivationCertificate with OpenAPI, then append only missing lineage/currentness fields at canonical owner.
3. Resolve refs through CAS and verify parent content, view, rule digest, tenant/use, verifier provenance, and epoch at governed projection.
4. Wire reviewer, API/client, MACHINE and audit to one resolved state; owner replay emits a new certificate and preserves superseded artifacts.

### Рассмотренные альтернативы

- **Treat equal bytes or copied certificate fields as current** — A parent may be revoked, a rule changed, or tenant/use altered while output bytes remain equal.
- **Add a parallel lineage database or recompute transforms in UI** — Duplicates CAS/provenance ownership and bypasses accepted N13b lifecycle.
- **Use one opaque stale boolean** — Hides which parent, rule, epoch, or tenant predicate failed and weakens replay.

### Free-grow и ресурсы

- **data or config growth:** New derived artifacts append exact parent/output refs and versioned derivation facts under existing certificate grammar.
- **extension boundary:** A new derivation semantic/protocol requires owner-approved typed extension and replay conformance; new parents within the relation are data.
- **resource behavior:** Resolve recorded refs within existing CAS/API limits. Incomplete lineage or capacity yields unknown/refused, never partial green.


### Миграция и восстановление

Version certificates additively; keep old records immutable and mark incompatible/stale records refused. Rollback disables the derived projection and retains prior artifacts and invalidation events; never restore authority from stale cache.


### Композиция и owners

- Certificate identity is content-bound to all exact parents, selected views, transform parameters, and rule version.
- Freshness independently resolves current parent heads, revocations, tenant/use, and epoch; certificate presence alone is insufficient.
- N13b owns producer, persistence, invalidation, and re-entry; UI owns projection only.


### Acceptance и различающие проверки

- Changing/revoking any parent makes the old view stale until owner replay creates a new artifact.
- Wrong view, omitted parent, changed rule digest, stale epoch, or tenant/use mismatch cannot pass even with copied fields/equal bytes.
- Remove resolver/invalidation but retain schema markers: replay witness fails.


### Входы и ответственность за их получение

- Accepted N13b persisted derivation and invalidation events.
- Exact CAS parent refs, selected views, current transform/rule version, permitted tenant/use, and active epoch.


### Когда обоснованно отклониться

- Without accepted persistence/replay, classify producer_missing/artifact_missing/bridge_missing precisely.
- If a parent/rule cannot be resolved, preserve historical record but refuse currentness.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [PROV-DM: The PROV Data Model](https://www.w3.org/TR/prov-dm/) — The model distinguishes entities, activities, usage, generation, derivation, attribution, time, and invalidation; these relations help describe exact lineage and lifecycle. **Граница:** PROV does not verify a producer, establish currentness or lawful use, or confer authority.
- [OpenAPI Specification 3.1.1](https://spec.openapis.org/oas/v3.1.1.html) — Schema Objects use JSON Schema; oneOf validates exactly one listed alternative. A discriminator is a selection hint and must not change validation, and alternatives must be listed explicitly beside oneOf. **Граница:** The specification does not guarantee a configured generator emits a correct client union or that clients validate hostile runtime payloads.
- [DSL Migration](https://martinfowler.com/bliki/DslMigration.html) — Versioned DSL change can use small incremental migration programs or version-specific parsers and a semantic model; migrations should preserve information important to authors. **Граница:** Practitioner guidance, not a PolicyOS schema decision; the native owner chooses the semantics.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="UI-08"></a>

## UI-08 — Add DS21 effect/world-growth readout after O1/O3

Исходная запись: [tasks.json](../tasks.json), `tasks[id=UI-08]`. Review: [root-review](root-review.md#UI-08).

### Предпочтительное решение

Build a read-only DS21 projection over actual GY-O1 confirmatory updates and GY-O3 versioned WorldModelRecord writes, gated on both outputs. Preserve the four owner cause classes prediction_error, implementation_failure, measurement_change, behavioral_response. Current WP-01/02 prohibit posterior mutation; after a competent scoped activation, the actual policy determines which admitted prediction_error/profile may change it; unresolved/compound diagnosis remains unresolved, and O2 anomalies remain candidate_unverified. Show deployment and acquisition origins as different provenance on one versioned growing-world branch. The surface gains no deploy, rollback, acquisition, or recommendation control.

### Что переиспользовать

- `policy-engine/src/polisyos/runtime/http/routes/governed_projections.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `get_governed_projection`. Existing governed readout boundary.
- `policy-engine/src/polisyos/runtime/http/services/cycle_board_projection.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `Cycle Board projection`. Existing projection service; one owner contract.
- `policy-engine/apps/runtime-dashboard/src/features/runs/components/AtlasRunDeck.tsx@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `reviewer readout`. Existing consumer identified by UI-08.
- `policy-engine/docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `DS21 and GY-O1/O2/O3 source criteria`. Planning source records four cause classes and single-branch semantics.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Rebind actual O1/O3 artifact contracts and owner cause enum after E02; O2 remains optional and candidate-only.
2. Require O1/O3 to emit and persist the causal record with prediction, observed window, policy/deployment ref, cause, rule/calibration version, authority band, time, and world branch/head.
3. Project read-only records to reviewer, MACHINE/CLI, and audit from the same versioned output; retain distinct deployment/acquisition provenance.
4. Verify a full cause/origin matrix and prove that the current WP-01/02 prohibition preserves no posterior mutation; after an actual scoped activation, only its admitted cause/profile may update.

### Рассмотренные альтернативы

- **Infer cause from outcome direction or protective action** — Behavioral response/protection can mimic predicted effects and are not confirmation.
- **Flatten O2 anomaly candidates into posterior facts** — Candidate evidence is not confirmatory authority.
- **Create a separate acquisition world or second write-back path** — Splits one growing world and duplicates O3 ownership.

### Free-grow и ресурсы

- **data or config growth:** New deployment/acquisition observations append to the existing branch with distinct provenance and owner versions.
- **extension boundary:** New cause classes need GY owner rule/version and composition; a UI label cannot introduce one.
- **resource behavior:** Page historical events and report unresolved diagnosis; storage limits must not silently drop cause or provenance.


### Миграция и восстановление

Append versioned observations and preserve earlier posterior/world records. Rollback disables the readout but keeps event history; no event is rewritten as confirmed and no second branch is merged implicitly.


### Композиция и owners

- Under current WP-01/02 no posterior changes. After competent scoped activation, only the cause/profile admitted by the actual update policy may change it; prediction_error alone is not activation and other/unresolved contributors cannot be laundered into an effect.
- O2 remains candidate_unverified.
- O3 is one versioned branch; acquisition and deployment retain separate provenance.
- Any newly persisted cause/projection record is emitted by the existing O1/O3/native projection owner; UI reads it and does not create a second causal/world ledger.
- UI-08 never writes a causal record, world head or WMR. It resolves O1/O3-owned persisted artifacts; an existing projection/audit receipt is only a projection receipt, never another causal history.


### Acceptance и различающие проверки

- Exercise all four causes plus unresolved/compound diagnosis through actual O1/O3 persistence and the fresh consumer. Under current WP-01/02 there is no posterior mutation; after actual activation, enforce the selected cause/profile policy rather than infer authority from a prediction_error label.
- O2 is visibly candidate_unverified; protective response never becomes confirmation.
- Acquisition/deployment stay on one branch with distinct provenance and exact time/version refs.
- Remove O1/O3 binding while retaining markers: consumer witness fails.


### Входы и ответственность за их получение

- Accepted O1 confirmatory and O3 world-growth artifacts and rule versions.
- Deployment/acquisition event refs with exact policy, source, time, branch, and authority provenance.


### Когда обоснованно отклониться

- Without accepted O1 and O3, keep preparation only and report producer_missing/bridge_missing; O2 cannot substitute.
- Compound/unresolved cause stays unresolved.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [PROV-DM: The PROV Data Model](https://www.w3.org/TR/prov-dm/) — The model distinguishes entities, activities, usage, generation, derivation, attribution, time, and invalidation; these relations help describe exact lineage and lifecycle. **Граница:** PROV does not verify a producer, establish currentness or lawful use, or confer authority.
- [OpenAPI Specification 3.1.1](https://spec.openapis.org/oas/v3.1.1.html) — Schema Objects use JSON Schema; oneOf validates exactly one listed alternative. A discriminator is a selection hint and must not change validation, and alternatives must be listed explicitly beside oneOf. **Граница:** The specification does not guarantee a configured generator emits a correct client union or that clients validate hostile runtime payloads.
- [Withheld propositions: WP-01/02/03 and activation boundaries](../../../../../../policy-engine/docs/system-design-decisions/withheld-propositions-register.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  — WP-01 retains no posterior mutation pending its live producers and activation; WP-02 supplies no approved routine schedule. **Граница:** This recommendation does not change or activate a withheld proposition. Reconcile later ratification at accepted-source rebind.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="UI-09"></a>

## UI-09 — Route the complete DS19 estate, auxiliary obligations and negative lifecycle

Исходная запись: [tasks.json](../tasks.json), `tasks[id=UI-09]`. Review: [root-review](root-review.md#UI-09).

### Предпочтительное решение

Route the entire DS19 estate by stable source-row identity and current owner, preserving source status separately from program assignment. The complete pinned register has entries 261, subunits 2, supplemental_findings 60, seeded_negative_lifecycle 23. Use the existing 85-row atlas-auxiliary-obligations.json only as assignment/conflict companion for non-entry arrays, not another source register. Bind each row and exact criterion to a successor, accepted closure, obsolete, out_of_scope, or blocked/absent-unallocated state; never delete a row because of a new filename or negative label.

### Что переиспользовать

- `policy-engine/architecture/atlas_surfaces/frontend-disposition-register.json@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `four canonical arrays`. Complete source census; file SHA256 6998e9d58ace363a12e0b3740b8abd5575b422f9d5d491ad0f5c8146d8112189; observation commit 413c120e73c0323294997e767abbd1a1a7a5a226.
- `policy-engine/docs/plans/active/post-e02-r9-unified-implementation/inventory/atlas-auxiliary-obligations.json@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `85 assignment/conflict rows`. Planning assignment and conflict evidence, not source status or second register.
- `policy-engine/docs/plans/active/post-e02-r9-unified-implementation/workstreams/04-atlas.md@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `UI-09 owner dispatch`. Rebind exact owner and historical criterion before dispatch.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Recompute the four array counts from the complete pinned JSON and verify identifiers/criterion refs; do not rely on sampled search.
2. Join every row to source criterion/disposition, current owner slice, actual consumer, and accepted task/closure or explicit unresolved disposition.
3. Reconcile all 85 auxiliary decisions against source-array rows and resolve source conflicts before dispatch.
4. Dispatch only owner-sliced successors with exact path/semantic-owner leases; preserve source register and append task-journal routing evidence.

### Рассмотренные альтернативы

- **Route only the 261 entries** — Drops 85 subunit/supplemental/negative-lifecycle obligations.
- **Create a new unified register and delete old rows** — Duplicates source ownership and risks rewriting source status or losing negative evidence.
- **Use filename matches or task titles as closure** — Does not prove criterion identity, owner acceptance, or consumer migration.

### Free-grow и ресурсы

- **data or config growth:** New source rows append at canonical owner; routing decisions append in existing journal/auxiliary handoff.
- **extension boundary:** Only source owner changes register schema/arrays. New category needs an owner/census rule; router must not create one.
- **resource behavior:** Recompute the full JSON set at dispatch/closeout. If count or identity cannot be established, keep row unresolved.


### Миграция и восстановление

Do not rewrite/delete historical rows. Append routing evidence against the bound source digest; rollback leaves unaccepted rows open and blocked.


### Композиция и owners

- Source register remains truth for all four arrays; 85 auxiliary rows are assignment decisions, not accepted status.
- Rebind and strangle counts overlap.
- Negative-lifecycle label is a negative witness input, never a passed test.


### Acceptance и различающие проверки

- Complete-file census yields 261/2/60/23 array rows and routes every stable identity.
- Delete one route from each array, omit an open supplemental/seeded negative, or claim a negative label as a pass: admission fails.
- Every route names owner, actual consumer, and closure signal or explicit blocked/absent-unallocated status.


### Входы и ответственность за их получение

- Accepted source-register snapshot and exact original criteria/dispositions at E02 rebind.
- Owner-slice acceptance for each successor and accepted closure/obsolete/out_of_scope evidence.


### Когда обоснованно отклониться

- If arrays change after the pinned digest, stop affected dispatch and recompute denominator.
- If owner/source conflict is unresolved, leave affected row blocked; do not blanket-rebuild.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [Parallel Change](https://www.martinfowler.com/bliki/ParallelChange.html) — Expand/migrate/contract lets clients move incrementally before the old interface is removed; temporary dual support has coordination cost and needs a real completion point. **Граница:** The pattern does not justify permanently maintaining duplicate semantics or auto-upgrading historical authority.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="UI-11"></a>

## UI-11 — Route DS20-B B3 revision-CAS to Fabric/N13b

Исходная запись: [tasks.json](../tasks.json), `tasks[id=UI-11]`. Review: [root-review](root-review.md#UI-11).

### Предпочтительное решение

Keep DS20 as handoff and put the public revision-CAS in Fabric/N13b. Extend the existing scenario-head CAS shape into an owner API that receives a candidate bound to expected revision/content digest and checks the same revision at the mutation boundary. Return a durable receipt for candidate, tenant/resource, expected/committed head, rule version, and outcome. OPA/step-up may precede mutation, but only owner-side CAS closes the race; a lock released before persistence or HTTP post-check cannot make authorize-to-mutate atomic. If storage is PostgreSQL, compare-and-set within the transaction; for cross-store effects require an explicit persisted outbox/receipt or retain the limitation.

### Что переиспользовать

- `policy-engine/src/polisyos/runtime/http/resource_binding.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `pre-OPA resource binding`. Existing DS20 binding; UI-11 does not change HTTP authz owner.
- `policy-engine/src/polisyos/fabric/api.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `Fabric public facade`. Existing public owner surface named by UI-11.
- `policy-engine/src/polisyos/fabric/retrieval/service.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `Fabric revision-CAS owner site`. Proposed owner-approved path; no write until P0/N13b lease.
- `policy-engine/src/polisyos/runtime/http/services/control/run_lifecycle.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `scenario-head CAS reference shape`. DS20 B3 handoff reference, not replacement owner.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. At P0 bind Fabric/N13b current head, mutator, consumers, and whether persistence shares the transaction.
2. Expose one typed expected-revision CAS through the Fabric facade and route candidate-to-mutation through it.
3. Persist success/refusal receipt in owner transaction; stale revision, scope mismatch, or changed content refuses atomically.
4. Retire limitation only after owner consumer uses CAS; DS20 forwards result and adds no second lock.

### Рассмотренные альтернативы

- **HTTP pre-OPA bind followed by post-check** — The gap spans OPA and the mutation lock; downstream persistence can occur after lock release.
- **Long-lived distributed lock or OPA serialization** — Does not prove mutation and persistence share one atomic revision boundary.
- **Retry stale candidates on the latest revision automatically** — Silently changes the authorized candidate; caller must re-evaluate.

### Free-grow и ресурсы

- **data or config growth:** Resources gain revisioned heads and receipts under existing Fabric acquisition/candidate grammar.
- **extension boundary:** Only Fabric/N13b adds resource CAS semantics; DS20 remains a consumer.
- **resource behavior:** Conflict is a refusal/409. Serialization retry restarts the decision on a fresh candidate; it never promotes stale content.


### Миграция и восстановление

Add owner API/receipt before enabling consumer; keep old path explicitly limited until callers use CAS, then retire it. On rollback suspend admission/mutation and preserve receipts; do not restore an unlocked authority claim.


### Композиция и owners

- CAS predicate and actual mutation share one owner-controlled atomic boundary.
- Candidate bytes, tenant/resource, expected revision, authorization result, and receipt are linked.
- Cross-store effects need a persisted outbox/receipt protocol or atomicity stays unclaimed.


### Acceptance и различающие проверки

- Two independent callers with the same expected revision: exactly one mutates; the other refuses without effect.
- Change candidate/head after pre-OPA binding: owner CAS refuses despite a valid lock/OPA result.
- Remove runtime revision check while retaining fields: concurrency witness fails.


### Входы и ответственность за их получение

- Accepted Fabric/N13b CAS contract, actual store, and owner receipt.
- Exact OPA/step-up result and tenant/resource scope from DS20 consumer.


### Когда обоснованно отклониться

- If persistence is outside transaction without receipt/outbox, keep bridge_missing and do not claim atomic promotion.
- Any write-set change requires new semantic/path lease.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [PostgreSQL 18: Transaction Isolation](https://www.postgresql.org/docs/18/transaction-iso.html) — At Read Committed, a concurrent updater waits and re-evaluates the WHERE predicate on the committed row; Serializable provides serial execution for committed transactions but applications must handle retries after serialization failures. **Граница:** Docs do not prove DS20 wiring. Pin the deployed PostgreSQL major, schema, isolation level, transaction boundary, and app behavior.
- [PostgreSQL 18: Explicit Locking](https://www.postgresql.org/docs/18/explicit-locking.html) — Row-level FOR UPDATE locks block conflicting writers and lockers until transaction end. **Граница:** A lock does not cover mutation or persistence after its transaction ends or in another store.
- [PostgreSQL 18: UPDATE](https://www.postgresql.org/docs/18/sql-update.html) — UPDATE supports a conditional WHERE predicate and RETURNING values for rows actually updated, exposing whether an expected-revision comparison matched. **Граница:** A SQL example is not a Fabric capability receipt; a post-check or later mutation is outside its atomic boundary.
- [Parallel Change](https://www.martinfowler.com/bliki/ParallelChange.html) — Expand/migrate/contract lets clients move incrementally before the old interface is removed; temporary dual support has coordination cost and needs a real completion point. **Граница:** The pattern does not justify permanently maintaining duplicate semantics or auto-upgrading historical authority.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="UI-12"></a>

## UI-12 — Run DS20-B B5 in real PostgreSQL verification

Исходная запись: [tasks.json](../tasks.json), `tasks[id=UI-12]`. Review: [root-review](root-review.md#UI-12).

### Предпочтительное решение

Use the named real-PostgreSQL harness on a commissioned local or cloud environment, not a mock; location is not the PostgreSQL property. Against bound final DS20 source, run all four B5 predicates with two independent store/app instances and unique schemas: one step-up replay winner; one scenario mutation winner plus one 409; corrupted-head denial before OPA; and a fresh app rejecting an unheaded CAS artifact. Keep DS9 reservation proof separate. Without the real DSN/driver/two-store environment, retain environment_blocked and make no PostgreSQL claim; DS20 closure says current tests skip without a real DSN.

### Что переиспользовать

- `policy-engine/tests/unit/runtime/http/test_runtime_postgres_linearizability.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `four DS20-B5 PostgreSQL proofs`. Exact existing harness; not executed in this research task.
- `policy-engine/docs/plans/active/atlas-slices/DS20-server-authz-enforcement-closure.md@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `B5 proof and reproduction command`. Records four predicates and current blocked environment.
- `policy-engine/docs/plans/active/post-e02-r9-unified-implementation/workstreams/04-atlas.md@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `UI-12 B5 route`. Separates this proof from DS9 reservation proof.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Freeze/rebind accepted DS20 source, harness, command, database major, driver, isolation level and selected local/cloud real-PostgreSQL identity without printing secrets.
2. Run two independently created stores/apps against real PostgreSQL and isolated schemas; synchronize adversarial requests at mutation boundary.
3. Retain complete per-case and combined output, including skip/failure results.
4. Classify each actual outcome: missing required environment before execution is environment_blocked; executed assertion failure is FAIL, harness interruption/error is ERROR, intentional SKIP stays SKIP and unexecuted/missing cases stay UNRUN. Acceptance requires all four real-PG properties on the bound source; do not relabel their failures as unavailable infrastructure.

### Рассмотренные альтернативы

- **Mock, SQLite, one app, or one store** — Cannot exercise real row locks, uniqueness, persisted CAS heads, or cross-instance visibility.
- **Use SERIALIZABLE as blanket replacement** — It can abort transactions and requires retries; it does not prove handler order or fresh-app persisted-head validation.
- **Reuse DS9 reservation proof** — It is a distinct owner and property set.

### Free-grow и ресурсы

- **data or config growth:** Four named proof cases remain the acceptance set; pin database version/config and receipt identities per run.
- **extension boundary:** New linearizability properties require DS20 owner criteria; UI-12 does not expand authorization behavior.
- **resource behavior:** Bound concurrency to case processes/connections and schemas; keep retries explicit and preserve the losing outcome.


### Миграция и восстановление

No product migration implied. Retain harness and outcomes append-only in DS20 receipt. Source/environment changes invalidate the receipt; rerun exact cut. Never upgrade environment_blocked to pass.


### Композиция и owners

- Real PostgreSQL and independent app/store instances are required.
- Corrupted-head denial must precede actual OPA evaluation; assert the boundary, not a marker.
- New app must read persisted CAS state and reject an unheaded artifact.


### Acceptance и различающие проверки

- Replay: exactly one winner across two stores/apps.
- Scenario mutation: one mutation and one HTTP 409.
- Corrupted head: denial before OPA.
- Fresh app: rejects unheaded CAS artifact after new construction.
- A missing required environment/DSN is environment_blocked; SKIP/UNRUN remain their own incomplete outcomes; executed property failures are FAIL and harness errors are ERROR. Mock/single-store evidence cannot establish the required PostgreSQL property.


### Входы и ответственность за их получение

- Selected commissioned local or cloud real-PostgreSQL DSN/driver and permission for isolated schemas; cloud identity is required only for the cloud profile.
- Bound DS20 source/harness command and pinned server version/configuration.


### Когда обоснованно отклониться

- If one environment is unavailable, use another authorized real PostgreSQL local/cloud profile with the required independent instances; if none is available, record the exact environment blocker without relabeling product failures.
- If E02 rebind changes original predicates/harness, reconcile before executing.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [PostgreSQL 18: Transaction Isolation](https://www.postgresql.org/docs/18/transaction-iso.html) — At Read Committed, a concurrent updater waits and re-evaluates the WHERE predicate on the committed row; Serializable provides serial execution for committed transactions but applications must handle retries after serialization failures. **Граница:** Docs do not prove DS20 wiring. Pin the deployed PostgreSQL major, schema, isolation level, transaction boundary, and app behavior.
- [PostgreSQL 18: Explicit Locking](https://www.postgresql.org/docs/18/explicit-locking.html) — Row-level FOR UPDATE locks block conflicting writers and lockers until transaction end. **Граница:** A lock does not cover mutation or persistence after its transaction ends or in another store.
- [PostgreSQL 18: INSERT](https://www.postgresql.org/docs/18/sql-insert.html) — A unique conflict target and ON CONFLICT provide an atomic insert/update result under concurrency; RETURNING reports rows actually affected. A unique single-use token row can support one-winner replay handling. **Граница:** The SQL primitive does not prove the application uses it at the correct boundary or maps a loser to the required response.
- [PostgreSQL 18: UPDATE](https://www.postgresql.org/docs/18/sql-update.html) — UPDATE supports a conditional WHERE predicate and RETURNING values for rows actually updated, exposing whether an expected-revision comparison matched. **Граница:** A SQL example is not a Fabric capability receipt; a post-check or later mutation is outside its atomic boundary.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="UI-13"></a>

## UI-13 — Reconcile DS20 scorecard provenance through DS9

Исходная запись: [tasks.json](../tasks.json), `tasks[id=UI-13]`. Review: [root-review](root-review.md#UI-13).

### Предпочтительное решение

Reconcile exact DS20 source-cut receipt through existing DS9 intake/effect. Keep foreign producer trust in ops-config and require resolved content-bound evidence plus verifier provenance before scorecard affects approval. DS20 HTTP authorization is not persisted scorecard provenance, signed mandate, or dissent. Preserve N012 exposure receipt and final mandate/dissent as artifact_missing/consumer_missing until their real DS9 artifacts/readers exist; an unmerged branch must not be called merged by label or filename.

### Что переиспользовать

- `policy-engine/docs/plans/active/atlas-slices/DS9-human-decision-integrity.md@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `DS9 intake/effect owner`. Reuse its receipt/effect chain; no second ledger.
- `policy-engine/docs/plans/active/atlas-slices/DS20-server-authz-enforcement.md@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `DS20 N012 handoff`. HTTP authz is bounded to server half.
- `policy-engine/docs/plans/active/atlas-slices/DS20-server-authz-enforcement-closure.md@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `scorecard provenance and N012 residual`. Records missing verifier provenance and DS9 artifacts/consumers.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. At P0 bind source cut, branch/merge state, scorecard evidence, and DS9 verifier/effect contract.
2. Resolve actual scorecard through DS9 intake; verify content hash and verifier provenance; persist DS9 receipt.
3. Keep ops-config responsible for foreign producer trust; route approval consumer to DS9, not DS20 authz result.
4. Keep N012 unavailable until signed mandate/dissent/exposure artifacts and a real reader exist.

### Рассмотренные альтернативы

- **Promote CAS presence or caller producer name to provenance** — Reference/identity presence does not establish content or verifier provenance.
- **Treat DS20 authz as approval integrity** — Closure says HTTP half is closed while persisted scorecard provenance and DS9 mandate artifacts remain missing.
- **Create a UI scorecard trust ledger** — Duplicates DS9 effect and moves foreign trust from ops-config.

### Free-grow и ресурсы

- **data or config growth:** ops-config adds versioned trust entries; DS9 appends content-bound intake/effect receipts.
- **extension boundary:** New trust source needs ops-config policy; new approval semantics need DS9 and competent institutional evidence.
- **resource behavior:** Unknown producers and source cuts stay unavailable; do not cache effects across changed source/rule versions.


### Миграция и восстановление

Append receipts to exact source cuts; do not rewrite merge/authority history. Rollback hides effect and retains evidence; authz-only records never become approval evidence.


### Композиция и owners

- DS9 resolves/content-binds producer artifact and verifier provenance before effect.
- ops-config owns foreign trust; DS9 owns interpretation/effect; DS20 owns HTTP authorization.
- N012 stays artifact_missing/consumer_missing until actual artifacts/reader exist.


### Acceptance и различающие проверки

- Unmerged branch called merged, self-asserted provenance, or authz-only receipt refuses.
- Scorecard affects approval only after DS9 resolves/verifies exact content/provenance.
- Remove resolver but keep markers: DS9 negative fails.


### Входы и ответственность за их получение

- Exact merged source-cut evidence and scorecard content digest.
- ops-config producer-trust policy with verifier provenance.
- DS9 N012 exposure receipt and institutionally signed mandate/dissent when available.


### Когда обоснованно отклониться

- If merge state/provenance is not established, preserve unavailable/unknown.
- Do not infer N012 completion from HTTP permission coverage.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [PROV-DM: The PROV Data Model](https://www.w3.org/TR/prov-dm/) — The model distinguishes entities, activities, usage, generation, derivation, attribution, time, and invalidation; these relations help describe exact lineage and lifecycle. **Граница:** PROV does not verify a producer, establish currentness or lawful use, or confer authority.
- [Parallel Change](https://www.martinfowler.com/bliki/ParallelChange.html) — Expand/migrate/contract lets clients move incrementally before the old interface is removed; temporary dual support has coordination cost and needs a real completion point. **Граница:** The pattern does not justify permanently maintaining duplicate semantics or auto-upgrading historical authority.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="UI-14"></a>

## UI-14 — Route DS20-B Helm policy mirror to ops/deploy

Исходная запись: [tasks.json](../tasks.json), `tasks[id=UI-14]`. Review: [root-review](root-review.md#UI-14).

### Предпочтительное решение

Keep canonical Rego in ops/policy/policies/** and mirror/deployment contract with ops/deploy. Prefer removing the duplicate if Helm packaging can consume the canonical policy artifact directly; otherwise generate the chart mirror deterministically and emit a versioned manifest of path-normalized policy membership and raw-byte content digests, source commit, and chart digest. Gate rollout on equality of the complete source set and packaged mirror. Helm signature verification proves package integrity, not source-to-mirror equality.

### Что переиспользовать

- `policy-engine/ops/policy/policies@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `canonical DS20 policy source`. Canonical Rego; DS20 owns this contract. Directory scope; exact changed files require rebind.
- `policy-engine/ops/cloud/helm/polisyos-cell/policies@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `ops/deploy chart mirror`. Out-of-fence mirror; ops/deploy owns updates. Directory scope; exact changed files require rebind.
- `policy-engine/docs/plans/active/atlas-slices/DS20-server-authz-enforcement-closure.md@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `B1 canonical policy bridge`. Records stale mirror as bridge_missing/verification_missing.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Ops/deploy decides whether chart can reference canonical bundle; if yes, retire duplicate versionedly.
2. If copy is required, generate complete path set and sorted digest manifest tied to source commit/policy version.
3. Compare canonical and packaged paths/bytes, then verify chart package; mismatch blocks rollout.
4. Retain receipt with deployed chart identity/source version.
5. Normalize path spelling/order only and hash raw source/package bytes. Retain source commit, chart identity and concise full-set parity outcome with deciding comparison output; no normalized-content parity and no duplicated policy-content dump.

### Рассмотренные альтернативы

- **Manually copy Rego into chart** — Allows silent drift and unclear ownership.
- **Trust Helm signature alone** — A signed stale chart is intact but may contain stale policy.
- **Make DS20 own deployment mirror** — Source assigns mirror to ops/deploy and says DS20 does not change canonical authz.

### Free-grow и ресурсы

- **data or config growth:** New canonical policy paths enter generated full manifest and mirror automatically.
- **extension boundary:** Canonical policy owner adds authorization semantics; ops/deploy packages and syncs, not policy meaning.
- **resource behavior:** Compare all normalized paths/digests including deletions; incomplete set blocks rollout.


### Миграция и восстановление

Append versioned mirror receipts; retire duplicate only after deploy consumes canonical artifact. On mismatch, block or return to prior verified chart/source commit; never edit old receipts.


### Композиция и owners

- Canonical source authority remains ops/policy/policies/**; chart policy is derived.
- Manifest comparison proves source/mirror equality; Helm provenance proves package integrity/origin, separate predicates.
- Ops/deploy owns mirror generation and rollout gate.


### Acceptance и различающие проверки

- Stale, missing, extra, hand-edited, wrong-version, or removed source path fails parity.
- Changing mirror bytes while keeping metadata fails digest compare.
- Valid signature with stale embedded policy fails source parity.


### Входы и ответственность за их получение

- Approved canonical Rego source commit/version.
- Ops/deploy chart packaging and rollout criteria.
- Trust key/chart identity if signing is used.


### Когда обоснованно отклониться

- If packaging cannot consume source or emit complete deterministic manifest, keep bridge_missing/verification_missing and block rollout.
- If generated rendering is used, bind rendered artifact identity as mirror output.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [Helm Provenance and Integrity](https://helm.sh/docs/topics/provenance/) — Helm package provenance binds a chart package checksum to a signature, and helm install --verify aborts when verification fails. **Граница:** A valid signature does not prove an embedded policy mirror equals the canonical source policy set. The current page warns that it is not fully updated for Helm 4; only generic package checksum/signature integrity is relied on. Rebind command behavior to the actually deployed major before execution.
- [Parallel Change](https://www.martinfowler.com/bliki/ParallelChange.html) — Expand/migrate/contract lets clients move incrementally before the old interface is removed; temporary dual support has coordination cost and needs a real completion point. **Граница:** The pattern does not justify permanently maintaining duplicate semantics or auto-upgrading historical authority.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="UI-17"></a>

## UI-17 — Carry DS15 positive-route residual through existing acquisition owner

Исходная запись: [tasks.json](../tasks.json), `tasks[id=UI-17]`. Review: [root-review](root-review.md#UI-17).

### Предпочтительное решение

Prepare existing DS15 API/projection/client against the agreed exact interface; composed acquisition/action use requires its exact route, cutoff, facet, cost, rights and mandate predicates. Gross VOI display is gated on its own producer/basis and can remain available with cost unknown. Preserve lawful existing route and render refusal until inputs exist. Keep numeric VOI as a decision/utility measure with its own owner-produced value/ranking ref and basis; show actionable acquisition cost separately with its own schedule/ref. Do not calculate VOI in the client, infer a gap from more rows, subtract unknown cost, or claim net value without a named utility contract.

### Что переиспользовать

- `policy-engine/src/polisyos/runtime/http/routes/acquisitions.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `existing acquisition routes`. Existing route owner from UI-17.
- `policy-engine/src/polisyos/runtime/http/services/acquisition_surface_projection.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `acquisition status/refusal projection`. Existing consumer bridge.
- `policy-engine/apps/runtime-dashboard/src/features/runs/domain/acquisitionRoutePresentation.ts@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `acquisition route UI`. Existing client presentation owner.
- `policy-engine/src/polisyos/runtime/quality/acquisition_planner.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `canonical planner owner`. DS15 identifies planner as VOI/cost reference owner; exact interface rebind at P0.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Reconcile residual against N13a/N13b, exact route/cutoff/facet, rights, mandate, and native policy.
2. Route status/refusal and permitted artifacts through current projection; no auto/offline execution.
3. Display each canonical producer-backed metric independently: a valid gross VOI ref/basis may be shown with cost unknown; a cost field needs its own admitted basis, and net value/ranking/action requires the particular additional inputs its estimand and policy consume.
4. Qualify each numeric claim separately: show an admitted gross VOI value/basis even if acquisition cost is unknown, with the missing cost explicit. Net-value, price and protected acquisition claims remain unavailable when their own required cost/route/rights/mandate inputs are absent; do not make one valid number authorize the action.

### Рассмотренные альтернативы

- **Display acquisition cost as VOI or infer VOI from a ranking** — Cost is not expected decision value; DS15 calls numeric VOI producer_missing and ranking-only.
- **Calculate a new score in browser** — Creates a second planner and lets the surface choose metric/utility without owner authority.
- **Auto-run/offline acquisition on a guessed gap** — Rights, mandate, currentness, route/cutoff/facet, and N13b handshake remain binding.

### Free-grow и ресурсы

- **data or config growth:** New routes configure only inside accepted acquisition protocol and owner-admitted rights/cost/VOI grammar.
- **extension boundary:** A genuinely new transport or metric needs approved typed adapter/conformance; arbitrary plugins do not become authority.
- **resource behavior:** Unknown route/license/cutoff/cost/VOI stays unavailable; page exact facts and do not act on partial response.


### Миграция и восстановление

Keep existing lawful route and append route/cost/VOI receipts. Enable new positive claim only after upstream admission; rollback disables presentation and preserves receipts, no auto/offline execution.


### Композиция и owners

- VOI/ranking and acquisition cost have distinct types, owners, refs, bases, times, and rule versions.
- Net expected utility requires an explicit owner-approved utility/decision contract comparing separate figures.
- Only N13b owner evidence establishes production growth.


### Acceptance и различающие проверки

- Unknown license/mandate or route/cutoff/facet keeps refusal and cannot authorize/cache acquisition.
- Numeric VOI needs owner-issued content-bound value/ranking ref; cost is a separate field/unit.
- Ranking-only is not numeric VOI; removing rights/currentness gate with markers makes admission fail.


### Входы и ответственность за их получение

- Accepted source route, rights/license, mandate, cutoff/facet, and N13b re-entry artifacts.
- Canonical planner VOI/decision value and separately versioned actionable cost schedule/record.
- Decision utility if net benefit is claimed.


### Когда обоснованно отклониться

- Without exact route/cost basis, positive-route debt stays blocked; no guessed price/VOI.
- If VOI owner remains producer_missing, show status/refusal only.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [The Value of Information and Stochastic Programming](https://pubsonline.informs.org/doi/10.1287/opre.18.5.947) — Expected value of perfect information is an expected gain in the decision objective and an upper bound on what is worth spending to acquire the information. **Граница:** This perfect-information bound is not a numeric VOI producer for DS15's finite route or a cost schedule.
- [On the Value of Information Across Decision Problems](https://pubsonline.informs.org/doi/10.1287/deca.2024.0187) — Expected utility increase and buying price are distinct value-of-information measures and need not rank information sources identically across decision problems. **Граница:** The paper does not supply PolicyOS's missing utility, route, cost basis, or numeric producer.
- [PROV-DM: The PROV Data Model](https://www.w3.org/TR/prov-dm/) — The model distinguishes entities, activities, usage, generation, derivation, attribution, time, and invalidation; these relations help describe exact lineage and lifecycle. **Граница:** PROV does not verify a producer, establish currentness or lawful use, or confer authority.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="UI-18"></a>

## UI-18 — Route DS17 positive coverage and risk-spend residuals to GY-N11

Исходная запись: [tasks.json](../tasks.json), `tasks[id=UI-18]`. Review: [root-review](root-review.md#UI-18).

### Предпочтительное решение

Keep DS17's closed negative ledger and route positive coverage, live scope, N12 artifact, and real over-spend/Bayesian witnesses through GY-N11's owner-issued certificate. The governed projection consumes it only after resolving content, binding complete current scope/sequence, and checking verifier provenance. Positive output is reviewer/MACHINE/audit only; no public delta before DS12/13. Do not create a second ledger, synthesize missing scope, or emit sequence/family probabilities.

### Что переиспользовать

- `policy-engine/src/polisyos/runtime/http/routes/governed_projections.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `get_confidence_ledger_risk_spend_projection`. Existing projection named by UI-18.
- `policy-engine/docs/plans/active/atlas-slices/DS17-confidence-ledger-risk-spend.md@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `DS17 closed negative ledger`. Reuse its bounded negative result.
- `policy-engine/src/polisyos/pdc/_impl/gy_waist.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `PromotionRiskSpendRecord and PromotionRiskSpendSummary`. Current display model; positive certificate/scope require GY-N11 rebind.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Rebind GY-N11 positive scope, live enumeration, N12 and owner certificate; preserve DS17 negative boundary.
2. Have GY-N11 produce content-bound certificate from complete live scope and actual over-spend/Bayesian evidence.
3. Resolve certificate, denominator, sequence, and verifier provenance at governed projection; expose to reviewer, MACHINE, audit.
4. Keep public delta and unsupported sequence/family probability out of scope.

### Рассмотренные альтернативы

- **Treat certificate marker, synthetic example, or field name as positive coverage** — It proves form only and hides omitted scope or unverified producer.
- **Build Atlas positive ledger beside GY-N11** — Duplicates arithmetic and risks diverging from canonical owner.
- **Publish first-positive/family probability** — Source plan withholds that proposition; public delta waits for DS12/13.

### Free-grow и ресурсы

- **data or config growth:** GY-N11 adds owner-defined evidence and scope under versioned rules; projection only renders accepted records.
- **extension boundary:** New risk arithmetic/scope composition belongs to GY-N11/N12, not UI.
- **resource behavior:** Complete enumeration required; missing/oversized scope returns unavailable/limited, never partial numeric claim.


### Миграция и восстановление

Append positive owner certificates with scope/rule version and retain DS17 negative evidence. Rollback withdraws positive display and keeps negative result; do not rewrite old claims or grant public visibility.


### Композиция и owners

- Positive requires resolved, content-bound owner certificate, verifier provenance, and current live scope.
- N12, over-spend, and Bayesian witnesses are real persisted outputs; missing evidence stays missing.
- Projection is read-only and audience-bounded; no DS12/13 public delta.


### Acceptance и различающие проверки

- Missing scope, synthetic sample, stale sequence, or family probability cannot yield green/numeric claim.
- Positive appears only from current GY-N11 certificate; DS17 negative remains honest.
- Remove resolver but keep certificate marker: positive projection refuses.


### Входы и ответственность за их получение

- Accepted GY-N11 live-scope enumeration, certificate, N12 artifact, and real over-spend/Bayesian witnesses.
- DS12/13 public-surface acceptance only if separately proposed.


### Когда обоснованно отклониться

- Without positive owner output or verifier provenance, keep local negative and classify positive producer_missing/artifact_missing.
- Different denominator/audience needs owner decision, not second ledger.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [PROV-DM: The PROV Data Model](https://www.w3.org/TR/prov-dm/) — The model distinguishes entities, activities, usage, generation, derivation, attribution, time, and invalidation; these relations help describe exact lineage and lifecycle. **Граница:** PROV does not verify a producer, establish currentness or lawful use, or confer authority.
- [OpenAPI Specification 3.1.1](https://spec.openapis.org/oas/v3.1.1.html) — Schema Objects use JSON Schema; oneOf validates exactly one listed alternative. A discriminator is a selection hint and must not change validation, and alternatives must be listed explicitly beside oneOf. **Граница:** The specification does not guarantee a configured generator emits a correct client union or that clients validate hostile runtime payloads.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="UI-19"></a>

## UI-19 — Reconcile DS18 positive transition/currentness consumers

Исходная запись: [tasks.json](../tasks.json), `tasks[id=UI-19]`. Review: [root-review](root-review.md#UI-19).

### Предпочтительное решение

Reuse epoch_validity_cascade and decision_validity; keep positive DS18 transition unavailable until producer, configured GY-CR4 reader, and actual consumer are source-proven. At P0 bind selected claim/decision, publisher, API/MACHINE readers, full original DS18 denominator, CAP-04 source-change events, and LIF-02 duties. Distinguish DS18 requiredness from new R9 event classes. Current renders only from replayable reconciled transition and lineage; legacy branch, opt-in None, equal hash, caller label, or unappointed signer cannot establish authority.

### Что переиспользовать

- `policy-engine/src/polisyos/runtime/quality/epoch_validity_cascade.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `epoch validity cascade`. Existing currentness and perturbation owner.
- `policy-engine/src/polisyos/scientist/validation/decision_validity.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `decision validity`. Existing decision owner; compose, do not create another epoch engine.
- `policy-engine/docs/plans/active/post-e02-r9-unified-implementation/execution/07-scoped-readiness.md@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `UI-19 and LIF-02 readiness rule`. Acquisition UI-17 is insufficient for this property.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. At P0 reconcile DS18 closure with GY-CR4 unconfigured opt-in reader and exact source; name positive-transition producer and consumers.
2. Consume CAP-04 change events and LIF-02 duties through existing epoch cascade, retaining distinct causes/times.
3. Persist replayable versioned transition/lineage; configure real reader and route fresh claim/decision consumer plus API/MACHINE/audit.
4. Keep signers empty and protected currentness unavailable until external evidence exists.

### Рассмотренные альтернативы

- **Treat hash equality, legacy branch, or caller label as current** — These proxies do not prove source events, epoch origin, lineage, or reissue.
- **Use UI-17 acquisition status as currentness consumer** — Acquisition does not prove selected claim/decision state or lineage.
- **Add another epoch/currentness engine** — Duplicates existing cascade and decision-validity owner.

### Free-grow и ресурсы

- **data or config growth:** New CAP-04 event classes flow through owner-versioned cascade and append-only epoch/reissue history.
- **extension boundary:** New event semantics need CAP-04/LIF/DS18 owner composition; UI cannot add status or signer meaning.
- **resource behavior:** Reconcile complete lineage. Missing/unresolvable events degrade per owner rule; never drop an event to stay green.


### Миграция и восстановление

Append transitions/reissues and preserve old epochs and DS18 requiredness. Rollback marks surface unavailable/stale and preserves history; do not restore previous current label or signer authority.


### Композиция и owners

- Currentness requires accepted producer, configured reader, CAP-04 events, LIF-02 composition, and fresh consumer.
- Original DS18 denominator and new R9 event classes are separately identified and reconciled.
- Code does not appoint institutional signers.


### Acceptance и различающие проверки

- Only complete replayable denominator, accepted transition, current epoch, and lineage render current.
- Legacy branch, opt-in None, equal hash, caller label, missing event, or unappointed signer remains refused/unknown.
- Remove configured reader/lineage while leaving green marker: actual consumer fails.


### Входы и ответственность за их получение

- Accepted CAP-04 events and LIF-02 lifecycle records.
- DS18 positive producer, configured GY-CR4 reader, named API/MACHINE readers, and source-cut merge evidence.
- Institutional signer evidence only for claims that require it.


### Когда обоснованно отклониться

- Until producer/reader accepted, classify positive transition producer_missing/consumer_missing and keep unavailable.
- If exact surface or event denominator cannot be named at P0, block affected closure; UI-17 does not substitute.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [PROV-DM: The PROV Data Model](https://www.w3.org/TR/prov-dm/) — The model distinguishes entities, activities, usage, generation, derivation, attribution, time, and invalidation; these relations help describe exact lineage and lifecycle. **Граница:** PROV does not verify a producer, establish currentness or lawful use, or confer authority.
- [Parallel Change](https://www.martinfowler.com/bliki/ParallelChange.html) — Expand/migrate/contract lets clients move incrementally before the old interface is removed; temporary dual support has coordination cost and needs a real completion point. **Граница:** The pattern does not justify permanently maintaining duplicate semantics or auto-upgrading historical authority.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="UI-20"></a>

## UI-20 — Allocate and deliver DS15 promotion union and private issuer

Исходная запись: [tasks.json](../tasks.json), `tasks[id=UI-20]`. Review: [root-review](root-review.md#UI-20).

### Предпочтительное решение

After P0 binds exact DS5 table group and original named negative, extend the canonical promotion contract/generator and actual DS15 consumer together. Derive the generated discriminated union from native owner, handle every known variant exhaustively, and keep an internal module-private issuer that accepts only resolved content-bound owner evidence. A TypeScript private constructor/brand can prevent accidental caller construction, but runtime validation and verifier provenance still reject forged wire data; it is no institutional signature or mandate. Unknown/unhandled variants or stripped limitations remain candidate/limited.

### Что переиспользовать

- `policy-engine/src/polisyos/pdc/_impl/gy_waist.py@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `PromotionObligationClass and promotion owner evidence`. Observed Python-side vocabulary; exact DS5 TS contract/issuer site is unbound until P0.
- `policy-engine/docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `DS5 candidate status and GY-AQ1 owner boundary`. Planning source; not an institutional appointment.
- `policy-engine/docs/plans/active/atlas-slices/DS15-acquisition-routes.md@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `DS15 candidate/admission consumer`. Existing acquisition consumer; preserve candidate band.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Resolve exact original DS5 group/site, source owner, consumer, and named negative at P0; do not infer path from title.
2. Extend only canonical contract/generator and regenerate full API family for every owner-defined variant.
3. Add/extend private owner-module issuer that verifies content-bound evidence and preserves status/limitations; validate wire payloads at runtime and never trust caller brand.
4. Route DS15 through issuer and handle variants exhaustively; novel variants stay candidate-only until owner version/consumer ship.

### Рассмотренные альтернативы

- **Export a public constructor, trust caller tags, or rely on TS private modifier** — TS private is erased; shape/brand does not verify provenance.
- **Use one boolean promoted flag** — Drops mixed status, limitations, and owner evidence.
- **Rebuild DS12/DS14/DS18 successors** — Those owners are reused; UI-20 owns the remaining union/issuer property.

### Free-grow и ресурсы

- **data or config growth:** New variants are added at canonical owner, emitted by generator, and consumed exhaustively.
- **extension boundary:** New data/config variant within supported class is owner-versioned; new authority semantic requires competent decision and conformance, never arbitrary plugins.
- **resource behavior:** Validation follows finite union/evidence resolution. Unknown variants remain candidate/refused, no green default.


### Миграция и восстановление

Use native versioned expand/verify/retire path; do not upgrade historical meaning. Keep old clients through migration window, then retire old path after proof. Rollback suspends admission and preserves receipts; never restore authority through superseded path.


### Композиция и owners

- Only canonical internal issuer creates presentation object after content resolution and verifier provenance.
- Generated exhaustiveness is a consumer guarantee only; authority remains owner evidence and institutional signer/mandate is separate.
- Candidate path continues within permitted band; unknown variant/scope cannot promote.


### Acceptance и различающие проверки

- Every owner variant round-trips through native generator, API union, issuer, and DS15 consumer with status/limitations preserved.
- Forged union, public construction, novel variant, or stripped limitation cannot create authority/admission.
- Remove issuer or a generated guard while retaining labels: original DS5 negative and fresh consumer fail.


### Входы и ответственность за их получение

- P0 exact DS5 group/site, source owner, and original negative.
- Resolved owner-produced content-bound evidence and verifier provenance.
- Institutional mandate/signature only if separate protected claim requires it; private issuer cannot supply it.


### Когда обоснованно отклониться

- Without exact DS5 group/site/generator, keep allocation unresolved; no parallel speculative union.
- Without runtime evidence resolution beyond TS branding, report verification_missing and remain candidate-only.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [TypeScript Handbook: Narrowing and exhaustiveness](https://www.typescriptlang.org/docs/handbook/2/narrowing.html) — Literal discriminants narrow union members; never-based exhaustiveness makes a new variant fail compilation in an unhandled switch. **Граница:** Static exhaustiveness does not validate untrusted JSON at runtime or replace an API schema.
- [TypeScript Handbook: Classes](https://www.typescriptlang.org/docs/handbook/2/classes.html) — TypeScript private modifiers are erased and provide design-time checks; ECMAScript private fields, closures, and WeakMaps provide runtime privacy mechanisms. **Граница:** Runtime privacy does not authenticate a network payload or appoint an institution.
- [OpenAPI Specification 3.1.1](https://spec.openapis.org/oas/v3.1.1.html) — Schema Objects use JSON Schema; oneOf validates exactly one listed alternative. A discriminator is a selection hint and must not change validation, and alternatives must be listed explicitly beside oneOf. **Граница:** The specification does not guarantee a configured generator emits a correct client union or that clients validate hostile runtime payloads.
- [DSL Migration](https://martinfowler.com/bliki/DslMigration.html) — Versioned DSL change can use small incremental migration programs or version-specific parsers and a semantic model; migrations should preserve information important to authors. **Граница:** Practitioner guidance, not a PolicyOS schema decision; the native owner chooses the semantics.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.
