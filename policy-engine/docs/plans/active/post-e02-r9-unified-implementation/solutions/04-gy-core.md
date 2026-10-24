# Основные остатки GY: предпочтительные решения

R15: для GYD-30 обязательны также `r15_extension` в [tasks.json](../tasks.json), [технический full-cycle](15-technical-method-lifecycle.md) и [joint-model research](../research/heterogeneous-model-execution.md). Исходные criteria ниже сохранены; additions не создают второго owner.

Статус: engineering recommendations; product execution UNRUN. Реализация только после E02 acceptance и полного affected-scope rebind. Исходные критерии не сокращаются; [общие решения](00-shared-decisions.md) предотвращают второго owner. [Нормативные уточнения](decision-clarifications.md) остаются предложениями.

<a id="GYD-01"></a>

## GYD-01 — PR1a data receipt + PR1b protected pilot

Исходная запись: [tasks.json](../tasks.json), `tasks[id=GYD-01]`. Review: [root-review](root-review.md#GYD-01).

### Предпочтительное решение

Keep PR1a and protected PR1b separate on existing N9 v8 intake/epoch. PR1a is a real data-only N4-bound receipt. Resolve the exact already-approved ADR-0178/0179 amendments at the competent owner and implement them; propose a further amendment only if a genuine contradiction remains; protected modes only require S6 recomputed from all five original axes (measurability, aggregation, capacity feasibility, mandate, strategic response), each with verifier-reachable refutation-capable evidence; compose S8 frontier/generation normative admission, promotion-safety acceptance and S7 governed_pilot_eligibility HumanDecision bound to design/candidate, mode, S6/S8/safety digests or typed-empty values, mandate record/class/role, stop/rollback, validity and reviewer separation. S6 is necessary, not sufficient. Keep authentic GY-O0-NC-01 field-pilot near-miss separate; no fixture or unsafe trial substitutes it.

### Что переиспользовать

- `policy-engine/src/polisyos/runtime/quality/promotion_sequence.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `CanonicalN9PromotionPort`. Present at bounded static source observation only; rebind at accepted E02.
- `policy-engine/src/polisyos/runtime/quality/generation_cycle.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `N9 intake / epoch forwarding`. Present at bounded static source observation only; rebind at accepted E02.
- `policy-engine/src/polisyos/runtime/quality/generation_cycle.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `S6/S8/S7 seam`. Rebind actual producer profiles; no positive receipt is established.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Resolve amended ADRs and debt rows 485–487, 618–619; identify genuine capacity-feasibility/strategic-response producers, not absence by prose.
2. Trace and extend N9; persist all S6 axis evidence and recompute posture, then bind S8, safety and S7 digests.
3. Probe wrong source/epoch, missing batch, removed atom/binding; keep authentic near-miss as a separate criterion.

### Рассмотренные альтернативы

- **Global EvalSafety gate** — Original change is protected-mode scoped.
- **S6 alone promotes** — Omits S8, safety and S7.
- **Fixture as authentic near-miss** — Launders test data into an external event.

### Free-grow и ресурсы

- **data or config growth:** Profiles/evidence grow under five original axes via N9.
- **extension boundary:** New evidence meaning requires typed owner amendment; LLM output remains candidate.
- **resource behavior:** Bind one protected batch; missing/stale evidence remains blocked.


### Миграция и восстановление

Keep N9 v8 and executed standing; protected promotion rolls back to blocked on digest mismatch. PR1a does not close PR1b or near-miss.


### Композиция и owners

- S6 recomputes from persisted axes (P37/P38); S8 and safety bind same candidate.
- S7 is external human decision evidence, not PolicyOS authority.
- Keep PR1a, PR1b and GY-O0-NC-01 statuses distinct.


### Acceptance и различающие проверки

- PR1a and PR1b produce separate receipts; no wrong-source/epoch/batch promotion.
- S6 all-five-axis removal/refutation test changes actual consumer outcome.
- Authentic near-miss is not represented by a fixture.


### Входы и ответственность за их получение

- Competent ADR owner decision and protected scope.
- Real S6 capacity-feasibility and strategic-response producers/profiles.
- Authentic safe-to-observe near-miss or explicit owner criterion decision.


### Когда обоснованно отклониться

- If accepted ADR differs, resolve with its source owner. If event is unsafe/unavailable, retain unresolved; never waive or simulate.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [Safe Policy Improvement with Baseline Bootstrapping](https://proceedings.mlr.press/v97/laroche19a/laroche19a.pdf) — Bounds candidate changes and falls back to baseline for uncertain state-action regions under stated MDP/data assumptions. **Граница:** Guarantees do not transfer to public policy justification or permission.
- [PROV-O: The PROV Ontology](https://www.w3.org/TR/prov-o/) — Vocabulary for provenance entities, activities, agents and relations. **Граница:** Lineage is not truth, independence, admissibility or authority.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="GYD-02"></a>

## GYD-02 — D1 canonical catalog binding repair and reissue

Исходная запись: [tasks.json](../tasks.json), `tasks[id=GYD-02]`. Review: [root-review](root-review.md#GYD-02).

### Предпочтительное решение

Use Data Forge canonical writer to repair/reissue the four source-reported wrong resource/distribution bindings; recount after E02. Every resource ID must resolve to its actual distribution before MEASUREMENT consumes it. Keep curated GDP/WDI unit-period mismatch on separate D2/PR1 obligation; identity correction cannot invent provider facts. Prove planner/N9 behavior when binding is wrong or removed, not merely catalog shape.

### Что переиспользовать

- `policy-engine/src/polisyos/data_forge/domains/catalog/knowledge/search.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `DatasetCatalogGraph`. Present at bounded static source observation only; rebind at accepted E02.
- `policy-engine/src/polisyos/runtime/quality/acquisition_planner.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `canonical planner`. Present at bounded static source observation only; rebind at accepted E02.
- `policy-engine/src/polisyos/runtime/quality/promotion_sequence.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `_measurement_obligation`. Present at bounded static source observation only; rebind at accepted E02.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Recount complete current mismatches at accepted E02.
2. Reissue through canonical writer preserving source, distribution, units, period and validity.
3. Exercise planner/fetch consumer for correct and removed/wrong bindings; route GDP/WDI mismatch separately.

### Рассмотренные альтернативы

- **Patch historical four rows only** — May miss current rows and bypass canonical reissue.
- **Match by label** — Does not bind distribution or measurement semantics.

### Free-grow и ресурсы

- **data or config growth:** Conforming resource records grow in canonical catalog.
- **extension boundary:** New transport/measurement semantics needs typed adapter/conformance.
- **resource behavior:** Bound affected resources; unknown distribution/units blocks measurement.


### Миграция и восстановление

Append corrected versions; keep D1 blocked until complete and preserve prior records.


### Композиция и owners

- Resource ID resolves to actual distribution before fetch.
- Measurement binds identity and unit/period; reuse canonical owner (P27).


### Acceptance и различающие проверки

- Complete post-E02 set resolves; remove or corrupt binding and fetch/promotion refuses.
- GDP/WDI units/periods are not fabricated by identity repair.


### Входы и ответственность за их получение

- Canonical writer and authoritative distribution metadata; provider facts if absent.


### Когда обоснованно отклониться

- If denominator differs from four, use measured set. If facts are external, leave correction external and route blocked.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [PROV-O: The PROV Ontology](https://www.w3.org/TR/prov-o/) — Vocabulary for provenance entities, activities, agents and relations. **Граница:** Lineage is not truth, independence, admissibility or authority.
- [Shapes Constraint Language (SHACL)](https://www.w3.org/TR/shacl/) — Validates RDF graphs against declared shapes and emits reports. **Граница:** Shape conformance is not real-world truth or institutional act.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="GYD-03"></a>

## GYD-03 — C3 route and constraint composition with actual prerequisites

Исходная запись: [tasks.json](../tasks.json), `tasks[id=GYD-03]`. Review: [root-review](root-review.md#GYD-03).

### Предпочтительное решение

Wire real D0/staged intake, truthful requirement basis and independent EvalSafety/context through existing Foundry owner. Bounded inspection found ConstraintStoreIngestor: ingest rejects missing basis; produce persists recomputation or typed refusal; reconcile_method binds replay-verified output. Feed source-bound D0 and independent context to this owner and optimizer; no caller authority, second store or synthetic method result.

### Что переиспользовать

- `policy-engine/src/polisyos/runtime/quality/workspace/foundry_consumption.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `ConstraintStoreIngestor`. Found despite earlier unresolved-file note; rebind at accepted E02.
- `policy-engine/src/polisyos/foundry/methods/catalog/causal/_id_contracts.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `RequiredDataSpec`. Present at bounded static source observation only; rebind at accepted E02.
- `policy-engine/src/polisyos/runtime/quality/generation_cycle.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `D0 staged intake`. Present at bounded static source observation only; rebind at accepted E02.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Rebind actual intake, safety producer and owner.
2. Persist owner-computed basis or typed refusal and replay-verifiable result.
3. Carry D0/evidence into actual optimizer and run receipt.
4. Probe missing D0, fabricated basis, absent context and removed binding at real consumer.
5. Implement missing native producers/bridges/readers or enforcement inside the assigned scope after owner allocation; do not stop by classifying internal engineering as an external input. Real institutional appointments, authentic observations and permission facts remain separately sourced and cannot be fabricated.

### Рассмотренные альтернативы

- **New constraint store** — Existing owner is present (P27).
- **Client-supplied basis** — Tests declaration, not recomputed predicate.

### Free-grow и ресурсы

- **data or config growth:** Methods extend RequiredDataSpec grammar.
- **extension boundary:** New constraint semantics needs typed Foundry extension.
- **resource behavior:** Demanded stage only; missing basis returns typed refusal.


### Миграция и восстановление

Keep external artifacts external and current blocker until D0/context are admitted.


### Композиция и owners

- Basis is owner-recomputed, not caller asserted.
- D0, safety/context and method result bind one route.


### Acceptance и различающие проверки

- Real route reaches optimizer with source-bound evidence.
- Removing route/content/safety binding makes consumer refuse.


### Входы и ответственность за их получение

- Real D0/staged intake and independent EvalSafety/context.


### Когда обоснованно отклониться

- If basis cannot replay, retain refusal; identify canonical owner before any new store.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [PROV-O: The PROV Ontology](https://www.w3.org/TR/prov-o/) — Vocabulary for provenance entities, activities, agents and relations. **Граница:** Lineage is not truth, independence, admissibility or authority.
- [Shapes Constraint Language (SHACL)](https://www.w3.org/TR/shacl/) — Validates RDF graphs against declared shapes and emits reports. **Граница:** Shape conformance is not real-world truth or institutional act.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="GYD-04"></a>

## GYD-04 — K adjudicated correspondence accuracy

Исходная запись: [tasks.json](../tasks.json), `tasks[id=GYD-04]`. Review: [root-review](root-review.md#GYD-04).

### Предпочтительное решение

Keep correspondence outputs candidate-only until an independently appointed adjudicator labels an exact source-pinned denominator. Persist labels, candidate output, provenance, version, conflict/exclusion data; compute precision/recall over the complete set and report unavailable when owner or denominator is missing. ProviderFailoverPolicy is retrieval attempts, not semantic correctness; AxisEntailmentWitness is not final decider. Apply S0-K14 only when independent adjudicator correctness is claimed.

### Что переиспользовать

- `policy-engine/src/polisyos/scholar/search/providers.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `ProviderFailoverPolicy`. Retrieval attempts do not measure accuracy.
- `policy-engine/src/polisyos/scientist/evidence/claims@dccea950845cda5b38f026e7770c07819d31f4d9` — `AxisEntailmentWitness`. Candidate witness is not adjudication.
- `policy-engine/src/polisyos/runtime/quality@dccea950845cda5b38f026e7770c07819d31f4d9` — `K accuracy instrument`. No appointed owner/readback established.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Pin complete denominator and label rule.
2. Obtain competent adjudicator and independence scope.
3. Bind labels to source snapshot, compute full metrics, and emit receipt.
4. Probe self-score, present-null, partial denominator and witness-only; removal makes result unavailable.

### Рассмотренные альтернативы

- **Self-critique/failover scoring** — No independent ground truth.
- **Only labeled subset** — Incomplete denominator distorts accuracy.

### Free-grow и ресурсы

- **data or config growth:** Labels grow under versioned source-bound cases.
- **extension boundary:** New adjudication domain requires appointment; candidate labels never authority.
- **resource behavior:** If full denominator unavailable, report unavailable/limited.


### Миграция и восстановление

Preserve candidate-only state and prior receipts; withdraw current result if binding is removed.


### Композиция и owners

- Candidate, independent labels, denominator and adjudicator bind.
- Scope S0-K14 to this independent-correctness claim; avoid P14 inflation.


### Acceptance и различающие проверки

- Exact denominator and independent adjudication compute positive/negative accuracy.
- Missing owner, denominator, or binding returns unavailable.


### Входы и ответственность за их получение

- Independent K adjudicator and complete denominator/instrument owner.


### Когда обоснованно отклониться

- Absent appointment keeps gap; disputed denominator requires versioned re-evaluation.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [PROV-O: The PROV Ontology](https://www.w3.org/TR/prov-o/) — Vocabulary for provenance entities, activities, agents and relations. **Граница:** Lineage is not truth, independence, admissibility or authority.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="GYD-05"></a>

## GYD-05 — S3 source-backed legal-subject membership

Исходная запись: [tasks.json](../tasks.json), `tasks[id=GYD-05]`. Review: [root-review](root-review.md#GYD-05).

### Предпочтительное решение

Resolve legal-subject membership from independent CORR-B1 source and competent ruling, then feed source-bound membership scoped by subject, jurisdiction, context and period to current consumer. LegalSubjectMembershipSource and LegalCorrespondenceResult are reuse candidates after E02 rebind. PolicyOS may recompute defeasible purpose-scoped comparison; authority remains not_established until institutional ruling is consumed. Proposal map, wrong scope/time or unruled match stays blocked.

### Что переиспользовать

- `policy-engine/src/polisyos/scientist/evidence/claims@dccea950845cda5b38f026e7770c07819d31f4d9` — `LegalSubjectMembershipSource`. Present at bounded static source observation only; rebind at accepted E02.
- `policy-engine/src/polisyos/scientist/evidence/claims@dccea950845cda5b38f026e7770c07819d31f4d9` — `LegalCorrespondenceResult`. Comparison is not legal authority.
- `policy-engine/src/polisyos/runtime/quality@dccea950845cda5b38f026e7770c07819d31f4d9` — `legal correspondence consumer`. Present at bounded static source observation only; rebind at accepted E02.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Rebind CORR-B1/ruling interface and exact scope/time.
2. Ingest independent membership and ruling as separate evidence.
3. Recompute comparison only on matching source/version; probe source removal, proposal map, jurisdiction/time mismatch and unruled match.

### Рассмотренные альтернативы

- **Name correspondence as membership** — Text match is not sourced fact or ruling.
- **Sign caller assertion** — Signature cannot create institutional authority.

### Free-grow и ресурсы

- **data or config growth:** New subjects enter through canonical scoped source map.
- **extension boundary:** New legal regime/source needs typed adapter and owner.
- **resource behavior:** Scoped lookup only; stale/unruled fact downgrades/refuses.


### Миграция и восстановление

Keep candidate relation and authority blocked until ruling; append corrected source/ruling versions.


### Композиция и owners

- Membership and ruling are distinct.
- Comparison recomputed; authority changes only with admitted external act.


### Acceptance и различающие проверки

- Source-bound in-scope membership allows comparison.
- Removing source/ruling or changing scope/time blocks admission.


### Входы и ответственность за их получение

- CORR-B1 membership source and competent acceptance ruling.


### Когда обоснованно отклониться

- Disputed competence or textual-only source leaves authority not_established.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [PROV-O: The PROV Ontology](https://www.w3.org/TR/prov-o/) — Vocabulary for provenance entities, activities, agents and relations. **Граница:** Lineage is not truth, independence, admissibility or authority.
- [Shapes Constraint Language (SHACL)](https://www.w3.org/TR/shacl/) — Validates RDF graphs against declared shapes and emits reports. **Граница:** Shape conformance is not real-world truth or institutional act.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="GYD-06"></a>

## GYD-06 — J positive evidence-admission producer

Исходная запись: [tasks.json](../tasks.json), `tasks[id=GYD-06]`. Review: [root-review](root-review.md#GYD-06).

### Предпочтительное решение

Treat authentic positive producer as absent/unappointed. Appoint a source-bearing producer and bind real canonical-population input into native admission; only resolved evidence consumed by admission enters numerator. Synthetic control proves negative behavior only, never authentic positive. Keep exact a_spec_gap and zero numerator until source and owner exist; do not infer owner or promote empty population.

### Что переиспользовать

- `policy-engine/src/polisyos/scientist/evidence/claims@dccea950845cda5b38f026e7770c07819d31f4d9` — `canonical admission intake`. Consumer candidate only; authentic producer unappointed.
- `policy-engine/src/polisyos/scientist/orchestration/workflows@dccea950845cda5b38f026e7770c07819d31f4d9` — `population admission route`. Present at bounded static source observation only; rebind at accepted E02.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Obtain producer appointment, population and criterion.
2. Define typed artifact/provenance/scope/time/version and resolver.
3. Wire persisted real input to canonical intake and fresh consumer.
4. Use separate synthetic control to ensure fixture/empty/unscoped input is not numerator.
5. Implement missing native producers/bridges/readers or enforcement inside the assigned scope after owner allocation; do not stop by classifying internal engineering as an external input. Real institutional appointments, authentic observations and permission facts remain separately sourced and cannot be fabricated.

### Рассмотренные альтернативы

- **Count Slice-0 fixture** — Fixture cannot satisfy authentic positive.
- **Infer owner or use row presence** — Invents responsibility; presence is not admission proof (P32).

### Free-grow и ресурсы

- **data or config growth:** Records grow through canonical registry after appointment.
- **extension boundary:** New evidence type needs typed adapter and owner; no generic authority fallback.
- **resource behavior:** Source absence remains gap; no open-ended probing.


### Миграция и восстановление

Preserve a_spec_gap and zero numerator until real evidence is admitted.


### Композиция и owners

- Resolve/content-bind/verify provenance before numerator.
- Actual admission consumer decides membership.


### Acceptance и различающие проверки

- Real source-bound positive enters numerator.
- Fixture/empty/unscoped source remains outside.


### Входы и ответственность за их получение

- Appointed producer and real canonical population.


### Когда обоснованно отклониться

- If absent, retain gap; criterion change needs source-owner disposition.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [PROV-O: The PROV Ontology](https://www.w3.org/TR/prov-o/) — Vocabulary for provenance entities, activities, agents and relations. **Граница:** Lineage is not truth, independence, admissibility or authority.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="GYD-07"></a>

## GYD-07 — L current-family post-output GX

Исходная запись: [tasks.json](../tasks.json), `tasks[id=GYD-07]`. Review: [root-review](root-review.md#GYD-07).

### Предпочтительное решение

Recompute current-family GX post-output validator only after G1/G4/G5/N9-calibration owners resolve 38 routed reds. Preserve a_spec_gap if original validator allows. Clean failed job, suppression or wrong family is not closure. Persist actual findings and ProductionLoopRunProof; remove a required property while retaining markers and downstream GX must fail (P29).

### Что переиспользовать

- `policy-engine/src/polisyos/runtime/quality@dccea950845cda5b38f026e7770c07819d31f4d9` — `WorkspaceLoop`. Present at bounded static source observation only; rebind at accepted E02.
- `policy-engine/src/polisyos/runtime/quality@dccea950845cda5b38f026e7770c07819d31f4d9` — `ControlWorker`. Present at bounded static source observation only; rebind at accepted E02.
- `policy-engine/src/polisyos/runtime/quality@dccea950845cda5b38f026e7770c07819d31f4d9` — `GX current-family validator`. Rebind full family and finding denominator.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Resolve routed reds at named owners and retain inventory.
2. Run GX on actual post-output artifacts.
3. Probe suppression/wrong set/clean failed job.
4. Remove property while keeping marker; require consumer failure.
5. Implement missing native producers/bridges/readers or enforcement inside the assigned scope after owner allocation; do not stop by classifying internal engineering as an external input. Real institutional appointments, authentic observations and permission facts remain separately sourced and cannot be fabricated.

### Рассмотренные альтернативы

- **Whitelist reds** — Turns unresolved work into closure.
- **Skip because a_spec_gap** — Current-family post-output check remains required.

### Free-grow и ресурсы

- **data or config growth:** Family grows from source of truth.
- **extension boundary:** New family needs its real owner and validator.
- **resource behavior:** Complete scan; outstanding findings remain typed/routed.


### Миграция и восстановление

Keep executed standing and route reds; do not rewrite gap as pass.


### Композиция и owners

- Behavioral property/removal probe, not marker check (P29/P33).
- GX result and run proof bind same artifacts.


### Acceptance и различающие проверки

- Actual current family passes with no suppressed finding.
- Marker-preserving property removal fails.


### Входы и ответственность за их получение

- G1/G4/G5/N9-calibration owner repairs for routed findings.


### Когда обоснованно отклониться

- If set differs from 38, reconcile full set; exclusions need explicit owner disposition.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [Shapes Constraint Language (SHACL)](https://www.w3.org/TR/shacl/) — Validates RDF graphs against declared shapes and emits reports. **Граница:** Shape conformance is not real-world truth or institutional act.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="GYD-23"></a>

## GYD-23 — B/H terminal precedence and VOI measurement

Исходная запись: [tasks.json](../tasks.json), `tasks[id=GYD-23]`. Review: [root-review](root-review.md#GYD-23).

### Предпочтительное решение

Keep deterministic SeedTrajectoryPlanner and terminal precedence. Slice-0 operations are registry-derived BIND/ESTIMATE/VERIFY; expectations come from Slice0FixtureManifest; BudgetVector uses only original §3.5.1 minimal subset. Both groundable and tourism paths persist FrontierSnapshot/SearchLedger. Groundable result is measurement-rooted grounded_partial_admissible at Estimate only; tourism ceiling honest; poor recall routes repair. Inactive ops, forced groundable, no-root partial, post-Estimate continuation, DesignCandidate, inline expectation, full playbook or extra budget field fail.

### Что переиспользовать

- `policy-engine/src/polisyos/pdc/_impl/gy_waist.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `SearchExitContract`. Present at bounded static source observation only; rebind at accepted E02.
- `policy-engine/src/polisyos/pdc/_impl/gy_waist.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `BudgetVector.slice0`. Preserve exact authorized minimal subset.
- `policy-engine/src/polisyos/pdc/_impl/gy_waist.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `VOISelectionAudit`. Present at bounded static source observation only; rebind at accepted E02.
- `policy-engine/src/polisyos/core/contracts/search.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `SearchLedger`. Present at bounded static source observation only; rebind at accepted E02.
- `policy-engine/src/polisyos/runtime/quality@dccea950845cda5b38f026e7770c07819d31f4d9` — `WorkspaceLoop / WorkspaceSearchLedger`. Present at bounded static source observation only; rebind at accepted E02.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Rebind registry, fixture manifest and §3.5.1 budget.
2. Persist root, frontier, ledger, VOI, terminal and port.
3. Check recall and stop at Estimate.
4. Probe all forbidden operations/fields, continuation and no-root variants.

### Рассмотренные альтернативы

- **Replace with CP-SAT/Z3** — No measured need; criterion pins deterministic planner; solvers prove encoded formulas only.
- **Trust terminal spelling** — Does not establish root, port or stopping rule.

### Free-grow и ресурсы

- **data or config growth:** Fixtures and operations grow only through committed manifest/registry.
- **extension boundary:** New op/algorithm needs owner criterion and semantic conformance.
- **resource behavior:** Bound deterministic run; exhaustion stays incomplete.


### Миграция и восстановление

Keep executed standing and deterministic planner; roll back if precedence changes.


### Композиция и owners

- Both paths have FrontierSnapshot/SearchLedger; actual measurement root and Estimate required.
- B01 claim-specific grounds; C01 exact validated joint witness only for actual property, never pairwise/marginal substitute; C02 allows justified plurality.


### Acceptance и различающие проверки

- Groundable partial only at measurement-root Estimate; tourism ceiling and poor-recall routing persist.
- Inactive op/no-root/post-Estimate/DesignCandidate/inline budget probes fail.


### Входы и ответственность за их получение

- Committed fixture manifest, operation registry, budget definition and real measurement root.


### Когда обоснованно отклониться

- If source changes after rebind, use exact authorized budget; later-port terminal always fails.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [CP-SAT Solver](https://developers.google.com/optimization/cp/cp_solver/) — Integer constraints and distinct OPTIMAL, FEASIBLE, INFEASIBLE, MODEL_INVALID and UNKNOWN statuses; UNKNOWN can mean incomplete/resource limited. **Граница:** Only encoded constraint search, not facts, causal validity or admissibility.
- [Programming Z3](https://z3prover.github.io/papers/programmingz3.html) — SAT/model queries, incremental scopes and tracked assumptions; unsat cores need not be minimal. **Граница:** Encoded formulas only; cannot validate source truth or grant authority.
- [Safe Policy Improvement with Baseline Bootstrapping](https://proceedings.mlr.press/v97/laroche19a/laroche19a.pdf) — Bounds candidate changes and falls back to baseline for uncertain state-action regions under stated MDP/data assumptions. **Граница:** Guarantees do not transfer to public policy justification or permission.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="GYD-24"></a>

## GYD-24 — D2/E applicability and acquisition bridge

Исходная запись: [tasks.json](../tasks.json), `tasks[id=GYD-24]`. Review: [root-review](root-review.md#GYD-24).

### Предпочтительное решение

Use canonical applicability and acquisition owners. Before fetch, evaluate all original 16 facets and rest.json/unpd/ukons. Compose RequiredDataSpec→DataNeedSpec→real ACQUIRE; pinned gap resolves to permitted fetch or exact rung-7 costed acquisition_required naming the missing distribution and cost. No one-facet sample, dropped connector, caller VOI or generic cost passes.

### Что переиспользовать

- `policy-engine/src/polisyos/foundry/methods/catalog/causal/_id_contracts.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `RequiredDataSpec`. Present at bounded static source observation only; rebind at accepted E02.
- `policy-engine/src/polisyos/runtime/quality/acquisition_planner.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `canonical planner`. Present at bounded static source observation only; rebind at accepted E02.
- `policy-engine/src/polisyos/data_forge/domains/catalog/knowledge/search.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `DatasetCatalogGraph`. Present at bounded static source observation only; rebind at accepted E02.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Rebind full facet/connector set.
2. Persist applicability before fetch with evidence/time/version.
3. Resolve actual missing distribution; fetch or emit rung-7 costed exit.
4. Drop a facet/connector and try premature fetch/unbound cost; consumer must refuse.

### Рассмотренные альтернативы

- **New source contract/scheduler** — Parallel owner bypass (P27).
- **Representative sample** — Original set requires all facets/connectors.
- **Generic acquisition exit** — Must name actual distribution/rung/cost basis.

### Free-grow и ресурсы

- **data or config growth:** Conforming resources grow in canonical registry; Rule12 means zero CENTRAL code.
- **extension boundary:** New transport/semantics needs typed adapter/conformance.
- **resource behavior:** Bound declared set and pinned gap; unknown stays limited.


### Миграция и восстановление

Preserve existing planner/spec owners; unsupported connector leaves exact gap.


### Композиция и owners

- Applicability precedes fetch and binds complete basis.
- ACQUIRE binds missing distribution, cost and VOI.
- Recompute predicate, not caller declaration (P37/P38).


### Acceptance и различающие проверки

- All 16 facets and three connectors admitted before fetch.
- Actual acquisition or exact costed rung-7 exit; no facet omission.


### Входы и ответственность за их получение

- Original facet/connector definition, supported capabilities and cost data.


### Когда обоснованно отклониться

- If criterion changes, version and rebind all consumers; name-only connector does not pass.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [Policy Language | Open Policy Agent](https://www.openpolicyagent.org/docs/policy-language) — Rego declaratively evaluates policy over structured data. **Граница:** Rule evaluation does not supply causal grounds, evidence custody or admissibility.
- [MLIR Language Reference](https://mlir.llvm.org/docs/LangRef/) — Multiple dialects can coexist in a module, an analogy for typed stages over common IR. **Граница:** Compiler analogy only; not policy semantics or reason to adopt MLIR.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="GYD-25"></a>

## GYD-25 — D3 governed semantic adequacy benchmark

Исходная запись: [tasks.json](../tasks.json), `tasks[id=GYD-25]`. Review: [root-review](root-review.md#GYD-25).

### Предпочтительное решение

Extend SemanticAdequacyGate over committed benchmark. Recompute precision@5, known-seed recall, negative controls and freshness from governed labels/source version. Observed gate computes metrics but freshness_ok defaults true; replace proxy with owner-derived freshness. Preserve threshold and route low recall to repair; removed seed/control, stale set or threshold miss changes consumer.

### Что переиспользовать

- `policy-engine/src/polisyos/runtime/quality@dccea950845cda5b38f026e7770c07819d31f4d9` — `SemanticAdequacyGate.evaluate`. Present at bounded static source observation only; rebind at accepted E02.
- `policy-engine/src/polisyos/runtime/quality@dccea950845cda5b38f026e7770c07819d31f4d9` — `layer3_gy_semantic_benchmark.json`. freshness_ok default is provenance risk; rebind.
- `policy-engine/src/polisyos/pdc/_impl@dccea950845cda5b38f026e7770c07819d31f4d9` — `semantic benchmark consumer`. Present at bounded static source observation only; rebind at accepted E02.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Pin full benchmark, labels and threshold source.
2. Derive freshness from canonical version/hash, not bool.
3. Persist metrics, misses, controls and route.
4. Remove item while markers remain; test stale, irrelevant control and low-recall cases at consumer.

### Рассмотренные альтернативы

- **Keep freshness_ok=True** — Tests declaration, not freshness (P37/P38).
- **Inline threshold/similarity=1** — Masks recall/control failures.
- **Second benchmark runner** — Existing gate owns property.

### Free-grow и ресурсы

- **data or config growth:** Labels and controls grow in governed benchmark.
- **extension boundary:** New claim semantics requires owner decision; model output stays candidate.
- **resource behavior:** Complete benchmark required; incomplete is stale/limited.


### Миграция и восстановление

Keep benchmark history; mark prior receipts stale when source set changes.


### Композиция и owners

- Set, labels, freshness derivation and result bind.
- Negative/seed removal probes test semantics (P29/P33).
- S0-K14 only if independent evaluator correctness is claimed.


### Acceptance и различающие проверки

- Irrelevant control rejects; known seed is found; low recall routes repair.
- Freshness source change invalidates result.


### Входы и ответственность за их получение

- Committed labels, controls, threshold and freshness owner.


### Когда обоснованно отклониться

- Missing provenance leaves unverified; set change requires recompute.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [Shapes Constraint Language (SHACL)](https://www.w3.org/TR/shacl/) — Validates RDF graphs against declared shapes and emits reports. **Граница:** Shape conformance is not real-world truth or institutional act.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="GYD-26"></a>

## GYD-26 — C2 judge-output binding and real-input verdict

Исходная запись: [tasks.json](../tasks.json), `tasks[id=GYD-26]`. Review: [root-review](root-review.md#GYD-26).

### Предпочтительное решение

Bind C2 verdict to actual judge output for the exact governed input, then consume through RunNormativeArbitrationNode and causal-graph reconciliation. Persist input identity/content, judge execution/version, output content/digest, provenance and verdict binding; resolve it afresh at consumer. The known counterexample is decisive: delete outputs but keep names/promote marker and consumer must refuse. Keep status candidate-only until proof exists.

### Что переиспользовать

- `policy-engine/src/polisyos/scientist/orchestration/workflows@dccea950845cda5b38f026e7770c07819d31f4d9` — `RunNormativeArbitrationNode`. Present at bounded static source observation only; rebind at accepted E02.
- `policy-engine/src/polisyos/runtime/quality/generation_cycle.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `reconcile_causal_graph`. Present at bounded static source observation only; rebind at accepted E02.
- `policy-engine/src/polisyos/runtime/quality/generation_cycle.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `WorkspaceLoop._phase2_data_causal_graph`. Present at bounded static source observation only; rebind at accepted E02.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Rebind actual producer, output and downstream consumer.
2. Persist content-bound output linked to exact input and version.
3. Require consumer to resolve and verify output bytes before verdict.
4. Probe deletion with names/marker retained, wrong input, stale output and removed binding.

### Рассмотренные альтернативы

- **Trust names/status/promotion marker** — Known live counterexample deletes output while retaining markers (P29/P38).
- **Use LLM summary alone** — Candidate summary is not underlying judge output.
- **New judge registry** — Extend orchestration owner.

### Free-grow и ресурсы

- **data or config growth:** New judge versions register as typed producers with bound inputs/outputs.
- **extension boundary:** New semantics requires owner-reviewed output contract; no generic judge_passed fallback.
- **resource behavior:** Reference content-addressed output; missing output short-circuits promotion.


### Миграция и восстановление

Keep candidate-only state; missing binding returns unresolved, append correction rather than overwrite history.


### Композиция и owners

- Verdict binds exact input, producer/run, output bytes and rule version.
- Fresh consumer resolves/content-verifies (P32); marker-preserving deletion fails (P29).
- Authority remains candidate until separate owners resolve.


### Acceptance и различающие проверки

- Real output for exact input changes downstream verdict.
- Delete output while keeping status/name/promotion marker; consumer refuses.


### Входы и ответственность за их получение

- Governed input, actual judge output, accepted rule version and consumer contract.


### Когда обоснованно отклониться

- If output cannot be retained/resolved, leave verdict unresolved; version change invalidates dependent results.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [PROV-O: The PROV Ontology](https://www.w3.org/TR/prov-o/) — Vocabulary for provenance entities, activities, agents and relations. **Граница:** Lineage is not truth, independence, admissibility or authority.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="GYD-27"></a>

## GYD-27 — I event-backed roles and Ring-2 refusal

Исходная запись: [tasks.json](../tasks.json), `tasks[id=GYD-27]`. Review: [root-review](root-review.md#GYD-27).

### Предпочтительное решение

Use AgentEventBridge and real tool loop for persisted role events, no-client refusal and VOI normalization; keep AgentDecisionRecord candidate-only. Bind role to runtime actor, run, tool invocation and artifacts, not transcript/mock. Enforce Ring-2 refusal at construction/admission using verifier provenance (gy_waist.assert_ring2_verifier_provenance), so caller cannot forge status by filling a field. Ring-1 remains proposal. Recompute VOI from declared basis; missing/biased basis is unknown/refused.

### Что переиспользовать

- `policy-engine/src/polisyos/pdc/_impl/gy_waist.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `AgentDecisionRecord`. candidate_only=True observed; does not establish event provenance.
- `policy-engine/src/polisyos/pdc/_impl/gy_waist.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `assert_ring2_verifier_provenance`. Present at bounded static source observation only; rebind at accepted E02.
- `policy-engine/src/polisyos/foundry/agent_sim@dccea950845cda5b38f026e7770c07819d31f4d9` — `AgentEventBridge.run_tool_loop_proposal`. Present at bounded static source observation only; rebind at accepted E02.
- `policy-engine/src/polisyos/foundry/agent_sim@dccea950845cda5b38f026e7770c07819d31f4d9` — `tool_loop.run_tool_loop`. Present at bounded static source observation only; rebind at accepted E02.
- `policy-engine/src/polisyos/pdc/_impl/gy_waist.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `VOISelectionAudit`. Present at bounded static source observation only; rebind at accepted E02.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Rebind bridge, event schema and consumer; create genuine tool-loop run.
2. Persist role/action events linked by run and content; no-client emits actual blocker.
3. Validate Ring-2 proof at construction/admission against trusted verifier provenance.
4. Normalize VOI from real basis; probe no-client, missing event, transcript-only role, forged verifier and biased VOI.

### Рассмотренные альтернативы

- **Transcript role labels** — Text is not runtime event/actor proof.
- **Downstream-only Ring-2 guard** — Other consumers can accept forged artifact; close class at construction/intake (P31).
- **Trust DTO validator** — Does not prove tool execution or consumer linkage.

### Free-grow и ресурсы

- **data or config growth:** Roles/tools register through versioned event grammar.
- **extension boundary:** New authority role/verifier requires typed provenance rule; caller/LLM cannot assign authority.
- **resource behavior:** Existing loop budget bounds events; missing data yields candidate/refusal.


### Миграция и восстановление

Preserve candidates and no-client blocker; schema migration must retain event identity/replay meaning.


### Композиция и owners

- Role from verified persisted event, not transcript.
- Ring-2 resolves, content-binds and verifies provenance at construction (P32); single boundary (P31).
- VOI binds source, denominator and time basis.


### Acceptance и различающие проверки

- Real role events reach consumer and candidate proposal.
- No-client refuses; agent cannot construct Ring-2; biased VOI has no authority.


### Входы и ответственность за их получение

- Real tool loop/client and actor events.
- Verifier appointment/provenance rule and original VOI basis.


### Когда обоснованно отклониться

- If event/verifier unavailable, stay candidate/refused; fail closed if self-attestation indistinguishable.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [PROV-O: The PROV Ontology](https://www.w3.org/TR/prov-o/) — Vocabulary for provenance entities, activities, agents and relations. **Граница:** Lineage is not truth, independence, admissibility or authority.
- [Safe Policy Improvement with Baseline Bootstrapping](https://proceedings.mlr.press/v97/laroche19a/laroche19a.pdf) — Bounds candidate changes and falls back to baseline for uncertain state-action regions under stated MDP/data assumptions. **Граница:** Guarantees do not transfer to public policy justification or permission.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="GYD-28"></a>

## GYD-28 — F2 secret/PII and CAS integrity surface

Исходная запись: [tasks.json](../tasks.json), `tasks[id=GYD-28]`. Review: [root-review](root-review.md#GYD-28).

### Предпочтительное решение

Complete F2 at actual raw/public and DAG/loop CAS producer and consumer. Keep secret/PII scan and byte integrity distinct: scan scoped outputs; verify canonical bytes, digest, dedup/ref, tamper, GC and dereference; separately bind admitted manifest.authority to each actual artifact and consumer. Valid digest and manifest shape still refuse/limit when authority missing, stale or for wrong boundary. Existing report fields do not prove route consumer uses them; use one shared intake/emission invariant, not one-site patches.

### Что переиспользовать

- `policy-engine/src/polisyos/runtime/quality@dccea950845cda5b38f026e7770c07819d31f4d9` — `scan_secret_and_pii`. Present at bounded static source observation only; rebind at accepted E02.
- `policy-engine/src/polisyos/runtime/quality@dccea950845cda5b38f026e7770c07819d31f4d9` — `SecretAndPIIScanReport`. Present at bounded static source observation only; rebind at accepted E02.
- `policy-engine/src/polisyos/runtime/quality@dccea950845cda5b38f026e7770c07819d31f4d9` — `build_cas_integrity_report`. Present at bounded static source observation only; rebind at accepted E02.
- `policy-engine/src/polisyos/runtime/quality@dccea950845cda5b38f026e7770c07819d31f4d9` — `CASIntegrityReport`. Present at bounded static source observation only; rebind at accepted E02.
- `policy-engine/src/polisyos/runtime/quality@dccea950845cda5b38f026e7770c07819d31f4d9` — `DAG/loop CAS producers and consumers`. Enumerate actual surfaces after source rebind.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Enumerate raw/public and DAG/loop outputs with complete file-type denominator.
2. Wire scan and CAS owner; bind authority purpose/scope/provenance/version/time separately from digest.
3. At actual consumer resolve authority and enforce boundary/freshness.
4. Probe nested secret, tamper, missing manifest, valid digest with missing/wrong/stale authority, GC/deref and marker-preserving property removal.

### Рассмотренные альтернативы

- **Digest or manifest presence proves authority** — Digest proves bytes, not permission; shape/self-attestation fails P32/P38.
- **New CAS or secret registry** — Duplicate owners instead of wiring actual consumers.
- **Patch single output site** — Sibling consumer reopens class (P31).

### Free-grow и ресурсы

- **data or config growth:** Conforming producers register scan and authority purpose through existing manifest grammar.
- **extension boundary:** New storage boundary/purpose needs typed adapter and conformance.
- **resource behavior:** Bounded streaming scan and dereference; uncertainty blocks/downgrades route.


### Миграция и восстановление

Preserve CAS objects and append reports; affected output remains blocked on integrity/authority failure.


### Композиция и owners

- Digest integrity and authority are separate proofs.
- Producer and consumer bind authority to actual artifact, purpose, boundary, provenance, version and time.
- P29 removal probe at consumer; P32 resolve/bind/verifier; P31 one intake/emission class repair.


### Acceptance и различающие проверки

- Valid digest but absent/wrong/stale authority refuses/limits real consumer.
- Tamper caught; referenced blobs survive GC and dereference; secrets caught.


### Входы и ответственность за их получение

- Authority issuer/purpose policy, actual surface corpus, CAS retention/dereference behavior.


### Когда обоснованно отклониться

- Undiscovered consumer or unavailable authority resolution leaves surface/verification incomplete.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [PROV-O: The PROV Ontology](https://www.w3.org/TR/prov-o/) — Vocabulary for provenance entities, activities, agents and relations. **Граница:** Lineage is not truth, independence, admissibility or authority.
- [Shapes Constraint Language (SHACL)](https://www.w3.org/TR/shacl/) — Validates RDF graphs against declared shapes and emits reports. **Граница:** Shape conformance is not real-world truth or institutional act.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="GYD-29"></a>

## GYD-29 — F3 time/source and 406-row reconciliation

Исходная запись: [tasks.json](../tasks.json), `tasks[id=GYD-29]`. Review: [root-review](root-review.md#GYD-29).

### Предпочтительное решение

Reconcile historical 406 candidate-positive rows against complete current source-derived set; 406 is not a cap. Every current row records producer/source, field path, status text, candidate-positive rule, firewall, exclusion reason, resulting boundary and false-exclusion review. Resolve through S12 dereference/downgrade and distinguish time roles/as-of; fresh timestamp is not authority. For each deciding predicate classify provenance recomputed, independently_reconciled, consumer_asserted, institutionally_supplied or not_established, freeze at admission, and fail authority-grade gates on last three. Require zero false exclusions or named repair tickets.

### Что переиспользовать

- `policy-engine/src/polisyos/runtime/quality/candidate_firewall.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `AuthorityCandidateInventoryRow`. Present at bounded static source observation only; rebind at accepted E02.
- `policy-engine/src/polisyos/runtime/quality/epoch_validity_cascade.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `EpochValidityTransitionProducer`. Present at bounded static source observation only; rebind at accepted E02.
- `policy-engine/src/polisyos/runtime/quality@dccea950845cda5b38f026e7770c07819d31f4d9` — `S12 reference resolution/downgrade consumer`. Rebind complete inventory and path.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Reconstruct complete candidate-positive set and file-type denominator; reconcile to historic 406.
2. Populate all required fields for every row and link source/producer/path.
3. Resolve content refs and time roles; emit downgrade/repair obligations for stale refs.
4. Classify all deciding predicates P37; omit firewall or false-exclude row and require failure.

### Рассмотренные альтернативы

- **Hardcode 406 cap** — Current set can change.
- **Aggregate count or IDs only** — Can hide missing row fields; P35 requires complete traversal/file denominator.
- **Fresh timestamp means current** — Conflates time roles and authority (P08).

### Free-grow и ресурсы

- **data or config growth:** Rows grow/shrink from current source set with full disposition.
- **extension boundary:** New candidate-positive rule requires owner/version and cannot bypass firewall.
- **resource behavior:** Complete bounded/partitioned traversal preserves total denominator; failed enumeration is not_established.


### Миграция и восстановление

Append corrections and preserve historical 406 baseline; any unreviewed row keeps inventory incomplete.


### Композиция и owners

- P35 full source-derived set/path/type denominator; P36 cite finding IDs.
- P37 predicate provenance frozen; fail closed on candidate/institution/not-established.
- State property, implementation and divergent case (P38); time roles distinct (P08).


### Acceptance и различающие проверки

- Every current row has all eight dispositions and false-exclusion review.
- Zero false exclusions or explicit tickets; omitted firewall/unreviewed row fails.


### Входы и ответственность за их получение

- Current source set, historic baseline, firewall/time criteria and independent review owner if required.


### Когда обоснованно отклониться

- Incomplete traversal means no reported zero/count; false exclusions route repair, repeated class miss widens mechanism (P40).


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [PROV-O: The PROV Ontology](https://www.w3.org/TR/prov-o/) — Vocabulary for provenance entities, activities, agents and relations. **Граница:** Lineage is not truth, independence, admissibility or authority.
- [Shapes Constraint Language (SHACL)](https://www.w3.org/TR/shacl/) — Validates RDF graphs against declared shapes and emits reports. **Граница:** Shape conformance is not real-world truth or institutional act.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="GYD-30"></a>

## GYD-30 — G canonical joint composition evidence

Исходная запись: [tasks.json](../tasks.json), `tasks[id=GYD-30]`. Review: [root-review](root-review.md#GYD-30).

### Предпочтительное решение

Reconcile PDC/IR duplicate CompositionCertificate to one canonical GY-G owner, then extend resolve_bind_verify and actual workflow consumers. Preserve two-chapter composition, feedback-decomposition refusal and grounded emergent cap. Measure source-derived full set of verified Ukraine method contracts/families through real caller, produced result and fresh consumer or exact original limitation; do not hardcode 13 or extrapolate first family. Non-first consumer removal with first family intact must fail. B01 grounds are claim-type-specific; C01 accepts exact validated joint derivation for actual whole-joint property, never pairwise/marginal substitute; C02 permits justified plurality. Prevent correlated evidence independence inflation.


### Что переиспользовать

- `policy-engine/src/polisyos/pdc/_impl/gy_waist.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `CompositionCertificate`. Duplicate with IR owner; reconcile before extension.
- `policy-engine/src/polisyos/ir/analytics/cross_graph.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `CompositionCertificate`. Do not create third type.
- `policy-engine/src/polisyos/pdc/_impl/layer2_design_search.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `S2 consumer`. Present at bounded static source observation only; rebind at accepted E02.
- `policy-engine/src/polisyos/scientist/evidence/claims@dccea950845cda5b38f026e7770c07819d31f4d9` — `verified_evidence canonical intake`. Present at bounded static source observation only; rebind at accepted E02.
- `policy-engine/src/polisyos/runtime/quality@dccea950845cda5b38f026e7770c07819d31f4d9` — `GY-G resolve_bind_verify`. Present at bounded static source observation only; rebind at accepted E02.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.


### Последовательность реализации

1. Select/confirm canonical owner and retire/delegate duplicate.
2. Build complete source-derived contract/family inventory and link caller→result→fresh consumer or exact limitation.
3. Bind certificate to verified evidence, actual joint property, rule/source version and workflow outputs.
4. Probe non-first consumer deletion; test exact joint witness vs pairwise-only and correlated derivations.


### Рассмотренные альтернативы

- **Third certificate type** — Deepens P27 duplication.
- **Pairwise/marginal substitute** — Does not prove whole-joint property (C01).
- **Single derivation only / count correlation independent** — Contradicts C02 and inflates independence (P14).


### Free-grow и ресурсы

- **data or config growth:** Families grow from source inventory, not fixed 13 code list.
- **extension boundary:** New joint semantics requires owner decision; ordinary contracts use canonical grammar.
- **resource behavior:** Coverage cost tracks full set; missing family remains unresolved.


### Миграция и восстановление

Preserve historic GY-G repair; keep invalid candidates unpromoted and do not merge GY-S2 claim.


### Композиция и owners

- Claim-type-specific grounds (B01); exact joint witness only for actual joint property, never pairwise/marginal substitute (C01); justified plurality (C02).
- Verified intake resolves/binds/verifies provenance.
- GY-G composition distinct from GY-S2 knowledge binding.
- Recover a stochastic invocation through its existing native intent/trial/attempt owner: bind the selected realization or method-qualified realization set to that intent and its accepted result. Late, duplicate or changed replies under the same intent remain attempt outputs, not additional independent evidence; preserve their actual outcomes/cost and dependence. A safe pure retry may reconstruct a qualified frozen stream/state or use a method-qualified replacement realization with an explicit successor basis and full failure/selection denominator. Do not silently replace an already referenced realization, use retry-until-favourable selection, or force every pure local retry into external-effect reconciliation. Only an explicit new replicate changes the replicate basis; independence still needs the method criterion. No universal one-draw-per-job restriction, RNG schema, new intent ledger or global result lock; see R16 C3/C5 R24 companion.


### Acceptance и различающие проверки

- All source-derived families reach actual workflow result/consumer or exact limitation.
- Deleting non-first consumer while first remains fails complete coverage.
- For the selected stochastic method, interrupt between evaluation and result persistence, retry the same native intent and deliver the old completion late. The fresh trial/reuse consumer resolves one accepted realization set for that intent, counts no extra independent replicate, and preserves failed/unknown attempts and selection effects. Qualified pure replay/replacement progresses without a generic human gate; an explicit new replicate has a distinct basis and declared dependence. Remove intent-to-realization/result binding but retain seed, retry and artifact markers: double counting or silent substitution must fail the discriminator.


### Входы и ответственность за их получение

- Complete verified family set, owner reconciliation, actual callers/results/fresh consumers.


### Когда обоснованно отклониться

- If count differs historical 13, reconcile measured set. Unproven joint property stays limited/contested.

Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.


### Исследование и предел переноса

- [MLIR Language Reference](https://mlir.llvm.org/docs/LangRef/) — Multiple dialects can coexist in a module, an analogy for typed stages over common IR. **Граница:** Compiler analogy only; not policy semantics or reason to adopt MLIR.
- [PROV-O: The PROV Ontology](https://www.w3.org/TR/prov-o/) — Vocabulary for provenance entities, activities, agents and relations. **Граница:** Lineage is not truth, independence, admissibility or authority.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="GYD-31"></a>

## GYD-31 — N-V ValueOuterSet consumer readback

Исходная запись: [tasks.json](../tasks.json), `tasks[id=GYD-31]`. Review: [root-review](root-review.md#GYD-31).

### Предпочтительное решение

Reuse ValueOuterSet and extend PDC bridge so S1, N8 and N6 actually use set semantics. Preserve identification_status, assumption_status, calibration_scope, DataTrust, WMR ref and epoch; width remains owner-derived (observed contract rejects supplied width). Missing status, sample-only, timeout, unknown identification or trust must become bounded set/unknown/blocked, never point estimate by relabeling. Type presence alone does not close; verify actual consumer operations.

### Что переиспользовать

- `policy-engine/src/polisyos/core/contracts/value_outer_set.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `ValueOuterSet`. Observed derives width/rejects supplied width; rebind.
- `policy-engine/src/polisyos/pdc/_impl/gy_waist.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `value bridge`. Present at bounded static source observation only; rebind at accepted E02.
- `policy-engine/src/polisyos/pdc/_impl/layer2_readiness.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `S1 consumer`. Present at bounded static source observation only; rebind at accepted E02.
- `policy-engine/src/polisyos/pdc/_impl/layer2_design_search.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `N8/N6 consumers`. Present at bounded static source observation only; rebind at accepted E02.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Rebind producer and all S1/N8/N6 consumers.
2. Carry required trust/identification/assumption/calibration/WMR/epoch fields end-to-end.
3. Make downstream valuation/comparison operate on set.
4. Probe missing status/sample/timeout/trust downgrade and marker-preserving set removal.

### Рассмотренные альтернативы

- **Second value DTO** — Duplicates canonical contract.
- **Caller-supplied width or point collapse** — Manufactures precision and hides identification uncertainty.

### Free-grow и ресурсы

- **data or config growth:** Grounds and calibration scopes grow through canonical registries.
- **extension boundary:** New value semantics needs contract+consumer evolution, no parallel DTO.
- **resource behavior:** Bound set operations; resource/evidence shortfall returns unknown/blocked.


### Миграция и восстановление

Preserve old artifacts with schema/epoch; refuse incompatible consumers rather than coerce to point.


### Композиция и owners

- Owner-derived width and source/trust fields reach consumers.
- Identification, assumptions, trust, calibration, WMR and epoch are semantic inputs.


### Acceptance и различающие проверки

- Width changes with grounding/identification/trust at actual consumer.
- Missing status/sample/timeout stays blocked or unknown; marker removal fails.


### Входы и ответственность за их получение

- Admitted valuation grounds, trust, calibration and actual consumer behavior.


### Когда обоснованно отклониться

- If consumers collapse set to point, retain limitation until bridge repaired.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [Towards Causal Model-Based Policy Optimization](https://arxiv.org/abs/2503.09719) — Studies SCM intervention simulation in policy optimization and spurious predictive correlations under shift. **Граница:** Preprint/RL results do not prove local capacity, institutional safety or acceptance.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="GYD-32"></a>

## GYD-32 — S0/S1 real substrate and free-grow

Исходная запись: [tasks.json](../tasks.json), `tasks[id=GYD-32]`. Review: [root-review](root-review.md#GYD-32).

### Предпочтительное решение

Extend canonical Data Forge registries and Foundry L1/L4/L5 ingestion to bind real populated Ukraine substrate into queryable content-addressed GlobalState/WMR. Include actual L4 registry and firm_fundamentals/distress/budget panels through L1 DCAT and L5; retain period_id, record_hash, schema_version and source_snapshot_id. Measure selected corpus/count read-only under permit; historic 8.8M is not current. Real substrate is required, not sparse/synthetic positive. Identification mode, trust, prewar/wartime schema regime/buffer and calibration mismatch must change actual ValueOuterSet or downgrade/refuse; proxy never becomes point by relabeling. Conforming resource registers with zero CENTRAL code (Rule 12).


### Что переиспользовать

- `policy-engine/src/polisyos/data_forge/domains/catalog/knowledge/search.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `DatasetCatalogGraph`. Present at bounded static source observation only; rebind at accepted E02.
- `policy-engine/src/polisyos/data_forge/domains@dccea950845cda5b38f026e7770c07819d31f4d9` — `L5 registries`. Exact modules require accepted-tree rebind.
- `policy-engine/src/polisyos/pdc/_impl/world_model_record.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `WorldModelRecord`. Present at bounded static source observation only; rebind at accepted E02.
- `policy-engine/src/polisyos/core/contracts/value_outer_set.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `ValueOuterSet`. Present at bounded static source observation only; rebind at accepted E02.
- `policy-engine/src/polisyos/foundry@dccea950845cda5b38f026e7770c07819d31f4d9` — `L1/L4/L5 ingestion path`. Present at bounded static source observation only; rebind at accepted E02.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.


### Последовательность реализации

1. Under permit, measure complete selected real-substrate/file denominator.
2. Trace L4 and three panels through L1 DCAT/L5 into content-addressed GlobalState/WMR.
3. Verify required identifiers survive query to consumer.
4. Vary trust, identification, prewar/wartime regime/buffer and calibration; require real set change/refusal.
5. Verify conforming resource registration with zero CENTRAL code.
6. Implement missing native producers/bridges/readers or enforcement inside the assigned scope after owner allocation; do not stop by classifying internal engineering as an external input. Real institutional appointments, authentic observations and permission facts remain separately sourced and cannot be fabricated.


### Рассмотренные альтернативы

- **Sparse synthetic fixture as completion** — Original positive needs real populated substrate.
- **One-off importer/parallel catalog** — Bypasses free-grow canonical owners.
- **Historic 8.8M count** — Not current permitted measurement.
- **Proxy point by relabeling** — Cannot manufacture identification.


### Free-grow и ресурсы

- **data or config growth:** Conforming resource grows through canonical registries with zero CENTRAL code.
- **extension boundary:** Rule12 applies within supported semantics/protocol; new transport/meaning needs typed adapter and conformance.
- **resource behavior:** Permitted bounded read only; unknown trust/schema widens/refuses, no data copy.


### Миграция и восстановление

Keep source facts in owning systems, preserve WMR/history and references; failed binding leaves limited status.


### Композиция и owners

- DataForge facts, Foundry substrate and PDC WMR/value remain separate owners joined by explicit bridge.
- Same-slice/same-hash and all IDs survive.
- Mode/trust/regime/calibration changes actual set.
- S0-K14 only for an independent-correctness claim.


### Acceptance и различающие проверки

- Real populated source panels query through L1/L5 to GlobalState/WMR with required fields.
- Conforming new source registers without CENTRAL code; synthetic does not count.
- A single material counterexample outside the draft D2.3 examples can enter the native extension/research route without fabricated repetition or authority. Same-meaning resources remain data/config growth; changed protected semantics requires its actual owner rule and review, not a ratified label borrowed from an adjacent document.


### Входы и ответственность за их получение

- Permitted real Ukraine L4/panels, registry owners, access permit and corpus scope.


### Когда обоснованно отклониться

- No permitted source leaves positive unresolved. New semantic class may need typed adapter. Missing trust/schema widens/refuses.

Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.


### Исследование и предел переноса

- [MLIR Language Reference](https://mlir.llvm.org/docs/LangRef/) — Multiple dialects can coexist in a module, an analogy for typed stages over common IR. **Граница:** Compiler analogy only; not policy semantics or reason to adopt MLIR.
- [Dialect Conversion - MLIR](https://mlir.llvm.org/docs/DialectConversion/) — Conversion declares legal/illegal operations and explicit rewrite patterns, optionally type conversion. **Граница:** Structural translation does not verify meaning or authority.
- [PROV-O: The PROV Ontology](https://www.w3.org/TR/prov-o/) — Vocabulary for provenance entities, activities, agents and relations. **Граница:** Lineage is not truth, independence, admissibility or authority.
- [Shapes Constraint Language (SHACL)](https://www.w3.org/TR/shacl/) — Validates RDF graphs against declared shapes and emits reports. **Граница:** Shape conformance is not real-world truth or institutional act.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="GYD-33"></a>

## GYD-33 — S2 L2/L3 knowledge consumer binding

Исходная запись: [tasks.json](../tasks.json), `tasks[id=GYD-33]`. Review: [root-review](root-review.md#GYD-33).

### Предпочтительное решение

Keep Scholar as L2 knowledge/version/estimate owner and Lex as L3 threshold/amendment owner; use one binding bridge to exact N4/N8/N1/N2 consumers. Bind L2 confidence intervals, transport limits and contested edges; bind L3 thresholds with effective_from/as-of. Contested edge widens, transport limits applicability, amendment applies only at correct time. Require full source-derived denominator and consumer readback; graph presence/text is not authority. Keep GY-K appointment and GY-G family-coverage obligations separate.

### Что переиспользовать

- `policy-engine/src/polisyos/scholar@dccea950845cda5b38f026e7770c07819d31f4d9` — `Scholar L2 KG/version/estimates`. Native owner directory observed at this pin; exact output and consumer symbols must be bound after E02, not asserted from directory existence.
- `policy-engine/src/polisyos/lex/knowledge@dccea950845cda5b38f026e7770c07819d31f4d9` — `Lex L3 thresholds/amendments`. Native owner directory observed at this pin; exact output and consumer symbols must be bound after E02, not asserted from directory existence.
- `policy-engine/src/polisyos/runtime/quality@dccea950845cda5b38f026e7770c07819d31f4d9` — `N4/N8/N1/N2 binding bridge`. Present at bounded static source observation only; rebind at accepted E02.
- `policy-engine/src/polisyos/pdc/_impl/layer2_design_search.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `L2 consumer`. Present at bounded static source observation only; rebind at accepted E02.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Rebind source artifacts, versions, full denominators and semantics.
2. Keep writers separate; bridge typed artifacts with source/rule version and time.
3. Resolve actual L2/L3 at N4/N8/N1/N2 and propagate contested/transport/as-of status.
4. Remove non-first item, inject fake source, omit denominator, wrong effective date and bridge binding; require refusal/downgrade.
5. Implement missing native producers/bridges/readers or enforcement inside the assigned scope after owner allocation; do not stop by classifying internal engineering as an external input. Real institutional appointments, authentic observations and permission facts remain separately sourced and cannot be fabricated.

### Рассмотренные альтернативы

- **Merge Scholar and Lex writers** — Collapses distinct owners/time meanings.
- **Treat graph presence/text as proof** — No content-bound verified provenance.
- **Fold into K or GY-G** — Independent adjudication and composition coverage are distinct claims.

### Free-grow и ресурсы

- **data or config growth:** L2 edges and L3 amendments grow in separate versioned registries.
- **extension boundary:** New knowledge semantics/source protocol needs typed adapter; one bridge only.
- **resource behavior:** Resolve required subgraph/as-of threshold; incomplete denominator widens/refuses.


### Миграция и восстановление

Keep limited/executed status; append corrections; retain historic versions and separate GY-K/GY-G.


### Композиция и owners

- L2 evidence and L3 threshold are separately produced/versioned.
- Bridge resolves/binds/verifies provenance and as-of at real consumers.
- Contested/transport limits propagate; source text is not authority.


### Acceptance и различающие проверки

- Contested edge widens; transport limits; amendment binds as-of.
- Fake item, missing denominator, wrong date or removed bridge fails actual consumer.


### Входы и ответственность за их получение

- Scholar source/denominator; Lex threshold/amendment/effective time; accepted consumer contracts.


### Когда обоснованно отклониться

- If owner or time semantics unavailable, keep limitation; do not infer from partial graph.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [MLIR Language Reference](https://mlir.llvm.org/docs/LangRef/) — Multiple dialects can coexist in a module, an analogy for typed stages over common IR. **Граница:** Compiler analogy only; not policy semantics or reason to adopt MLIR.
- [Dialect Conversion - MLIR](https://mlir.llvm.org/docs/DialectConversion/) — Conversion declares legal/illegal operations and explicit rewrite patterns, optionally type conversion. **Граница:** Structural translation does not verify meaning or authority.
- [PROV-O: The PROV Ontology](https://www.w3.org/TR/prov-o/) — Vocabulary for provenance entities, activities, agents and relations. **Граница:** Lineage is not truth, independence, admissibility or authority.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.
