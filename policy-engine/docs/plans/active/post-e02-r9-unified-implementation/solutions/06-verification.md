# GY verification V1–V7: предпочтительные решения

Статус: engineering recommendations; product execution UNRUN. Реализация только после E02 acceptance и полного affected-scope rebind. Исходные критерии не сокращаются; [общие решения](00-shared-decisions.md) предотвращают второго owner. [Нормативные уточнения](decision-clarifications.md) остаются предложениями.

<a id="GYD-16"></a>

## GYD-16 — V1 complete moved-row coverage matrix

Исходная запись: [tasks.json](../tasks.json), `tasks[id=GYD-16]`. Review: [root-review](root-review.md#GYD-16).

### Предпочтительное решение

Extend the native capability coverage checker at its current owner boundary. Derive the full expected denominator from the complete accepted GY-acted obligation/path mapping, then join each row to real typed producer, persisted artifact/event, bridge, consumer, verifier, external/audit surface, and negative semantic evidence. Compare that derived set with the matrix; do not let the matrix declare its own completeness. The existing checker is a useful readout but, at the observed pin, a green matrix/summary can coexist with an omitted moved row or a removed runtime property. The deciding receipt should identify every row and evidence binding, and preserve uncovered rows as red/not_established rather than upgrading source status.

### Что переиспользовать

- `policy-engine/tools/quality/validation/check_layer3_gy_capability_coverage_matrix.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `existing matrix checker / capability coverage owner`. Loads the declared matrix and checks content/summary constraints; its denominator and behavioral chain need strengthening.
- `policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `§9 Phase 7 V1 criterion`. Defines all GY-acted rows as moved only when complete chain plus semantic test is covered.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. After accepted E02 rebind, derive the expected moved-row set from the complete canonical task/capability source and record its source path/hash and file-type denominator; reconcile disputed rows against the source owner before comparison.
2. For each row, resolve evidence to the actual owner and consumer, bind artifact/event bytes or canonical record, and record the semantic test that proves production and consumption.
3. Run one omitted-row falsifier and a matched remove-property/keep-matrix-marker mutation against the checker; both must turn the decision red.
4. Read the recomputed receipt and affected generated/public family from a fresh consumer. Keep matrix-only evidence labeled as such.

### Рассмотренные альтернативы

- **Add another hand-maintained completion registry** — It duplicates the capability matrix and can drift from the actual source denominator.
- **Accept row names, evidence links, or checker exit code as proof** — These are P38 proxies; they do not show a live capability or semantic consumer.

### Free-grow и ресурсы

- **data or config growth:** New GY obligations enter through the canonical task/capability owner and are recomputed into the denominator; row-specific evidence is added to the existing matrix format only after source-bound mapping.
- **extension boundary:** A new evidence kind or chain edge requires typed owner resolution and behavioral verification; arbitrary labels or self-attestation cannot extend coverage.
- **resource behavior:** Linear inventory/join over the frozen moved set; use one targeted omitted-row and one marker-preserving removal probe, then the shared final validator wave. Missing members fail as not_established.


### Миграция и восстановление

Do not rewrite §8.5 statuses or historical claims from this readout. Keep the existing matrix available; if recomputation or consumer resolution fails, retain a red/limited row and revert only the checker extension, not the evidence history.


### Композиция и owners

- The denominator is recomputed from accepted source, not inferred from matrix count or verifier declarations.
- Completeness requires producer through surface plus behavioral semantic evidence; row count alone is insufficient.
- Same-code recomputation establishes consistency; an independent oracle is needed only for claims that are explicitly independent correctness/authority checks.


### Acceptance и различающие проверки

- Positive: every moved row resolves to a real producer/artifact/bridge/consumer/verifier/surface and a negative semantic test.
- Adversarial: remove a source row while leaving the matrix intact; the denominator mismatch is red.
- Removal: delete the real consumer/property but retain all markers and links; the behavioral evidence fails.


### Входы и ответственность за их получение

- Actual E02 accepted tree and complete GY-acted source denominator; both remain not established in this preparation.


### Когда обоснованно отклониться

- If an original row cannot be source-bound, leave its disposition not_established and request canonical owner resolution rather than treating it as not applicable.
- If new evidence reveals consumer or generated-surface gaps, expand the exact affected closure under the existing task/resource permit; do not add a global gate.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [GY engine subordination plan, §9 Phase 7 verification criteria](../../../../../../policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` · #phase-7 — The original V1–V7 criteria, including V4 negatives a–v, define the evidence this proposal must preserve. **Граница:** Historical planning source; its implementation and product verification status remain planned_after_E02_acceptance and UNRUN in the assigned input. Rebind to the accepted E02 source before execution.
- [R9/GY/Atlas workstream 03, GY tasks](../../../../../../policy-engine/docs/plans/active/post-e02-r9-unified-implementation/workstreams/03-gy.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  — The workstream preserves task timing, formal status conflicts, final freeze/replay ordering, shared artifacts and no-duplicate-wave requirements. **Граница:** Planning evidence only; it cannot establish a product result or accepted tree.
- [Execution 07 scoped readiness and edge decisions](../../../../../../policy-engine/docs/plans/active/post-e02-r9-unified-implementation/execution/07-scoped-readiness.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  — Accepted-source rebind must resolve exact source, affected consumers, schemas/rules and relevant semantic fields; interface agreement is planning only. **Граница:** Does not turn verification preparation into a global completion barrier or substitute for the named final execution receipt.
- [GY capability coverage matrix checker](../../../../../../policy-engine/tools/quality/validation/check_layer3_gy_capability_coverage_matrix.py) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  — A native matrix checker exists and can be extended at its current ownership boundary. **Граница:** At the historical observation it validates declared matrix content and derived summaries; it does not itself establish the complete moved-row denominator or that each declared capability is behaviorally present and consumed.
- [Toward Just-in-time and Language-agnostic Mutation Testing](https://labs.oracle.com/pls/apex/f?p=LABS%3A0%3A111432938371215%3AAPPLICATION_PROCESS%3DGETDOC_INLINE%3A%3A%3ADOC_ID%3A3081) — Mutation testing checks whether tests detect injected faults; full campaigns can be expensive, motivating focused and incremental mutants. **Граница:** A surviving or killed mutant speaks only to that mutation and test oracle; a small targeted set does not estimate all defect coverage.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="GYD-17"></a>

## GYD-17 — V2 real B2 end-to-end loop proof

Исходная запись: [tasks.json](../tasks.json), `tasks[id=GYD-17]`. Review: [root-review](root-review.md#GYD-17).

### Предпочтительное решение

Use one authorized real-input production B2 trigger through the canonical HTTP ControlWorker → WorkspaceLoop path, with real CAS persistence, then have a fresh consumer resolve and read back the complete WorkspaceContract, artifact graph, SearchLedger, FrontierSnapshot, and typed SearchExitContract with their expected canonical hashes. A ProductionLoopRunProof can establish that the production route was exercised; it cannot stand in for measurement-rooted grounding, actual artifact persistence, or the downstream consumer. The V2 positive outcome must be either the criterion's grounded/partial result with its evidence root or a replayable, certified honest ceiling. A helper, committed fixture, synthetic case, or cleanly failed job is not a positive. The existing WorkspaceLoop refusal path is known to show source attempts and an S1 refusal, not scientific support, measurement coverage, or model execution; count it only if the final bound evidence satisfies the exact honest-ceiling clause.

### Что переиспользовать

- `policy-engine/src/polisyos/runtime/http/services/control/run_lifecycle.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `ControlWorker production lifecycle`. Production entry reaches the canonical ControlWorker.
- `policy-engine/src/polisyos/runtime/quality/workspace/loop.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `WorkspaceLoop.run_production_case`. Canonical real-CAS path distinguishes production evidence from fixture execution and records refusal-path limits.
- `policy-engine/src/polisyos/runtime/quality/authority.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `ProductionLoopRunProof`. Typed route proof is an input to, not a substitute for, the full end-to-end result.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Rebind trigger, authorization, case and persistence semantics to the accepted E02 source; select the smallest permitted real case that can produce the required evidence without broad exploration.
2. Exercise the HTTP production entry once, capture the run identity and route proof, then resolve persisted records from CAS rather than trusting in-memory worker returns.
3. Read each required artifact through its real downstream consumer; verify input, rule/schema and provenance bindings and recompute content hashes over resolved bytes.
4. Have the authorized evidence owner independently validate the measurement root or certify the honest ceiling; label a route-only/refusal-only result not_established for V2 if it misses that criterion.

### Рассмотренные альтернативы

- **Call WorkspaceLoop.run_fixture or a helper directly** — It bypasses production trigger and cannot establish the required real-input route.
- **Treat ProductionLoopRunProof or a green worker exit as whole-loop evidence** — Those establish route/execution facts only and are proxy evidence for measurement and consumer use.
- **Repeat multiple full production cases to strengthen confidence** — It consumes CAS/worker capacity and duplicates the V3/V7 inputs; one criterion-bearing case should feed the shared evidence chain.

### Free-grow и ресурсы

- **data or config growth:** Additional genuine cases may be admitted under the existing production-input and authorization contract; keep their source, audience, time, rules and provenance bound.
- **extension boundary:** New trigger or artifact semantics require a typed, authorized owner extension; test fixtures cannot be relabeled as production evidence.
- **resource behavior:** One authorized production invocation; reuse its persisted artifacts for V3, V5 and V7 where source/case identity matches. Fail closed on missing root, CAS readback, or fresh consumer.


### Миграция и восстановление

Preserve failed and refusal records as non-authority evidence. Do not manufacture a denominator or promote an existing refusal to a success; if persistence or source binding fails, retain the run receipt as partial diagnostic evidence and V2 as UNRUN/not_established.


### Композиция и owners

- Production route proof, measurement-root proof, persisted artifact, and consumer readback are distinct claims with explicit provenance.
- CAS digest verification binds bytes; semantic validity and authority require the relevant evidence owner/verifier.
- Same-code replay can confirm consistency without introducing a second complete loop implementation.


### Acceptance и различающие проверки

- Positive: actual B2 HTTP trigger on a permitted real case produces the named artifacts, and a fresh consumer resolves them with consistent hashes and provenance.
- Adversarial: fixture/helper input or clean job failure cannot satisfy the production property.
- Removal: disable durable trigger, CAS persistence, measurement root, or consumer resolution in matched probes; each breaks its own proof plane.


### Входы и ответственность за их получение

- Accepted E02 source, authorized real case, production access, and the actual measurement/evidence owner or certified ceiling evidence.


### Когда обоснованно отклониться

- If only the existing refusal path is available and it does not meet the exact honest-ceiling condition, record that as a bounded result and leave V2 open.
- If the production path emits new artifacts after rebind, extend readback to those real consumers without silently widening the product claim.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [GY engine subordination plan, §9 Phase 7 verification criteria](../../../../../../policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` · #phase-7 — The original V1–V7 criteria, including V4 negatives a–v, define the evidence this proposal must preserve. **Граница:** Historical planning source; its implementation and product verification status remain planned_after_E02_acceptance and UNRUN in the assigned input. Rebind to the accepted E02 source before execution.
- [R9/GY/Atlas workstream 03, GY tasks](../../../../../../policy-engine/docs/plans/active/post-e02-r9-unified-implementation/workstreams/03-gy.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  — The workstream preserves task timing, formal status conflicts, final freeze/replay ordering, shared artifacts and no-duplicate-wave requirements. **Граница:** Planning evidence only; it cannot establish a product result or accepted tree.
- [Execution 07 scoped readiness and edge decisions](../../../../../../policy-engine/docs/plans/active/post-e02-r9-unified-implementation/execution/07-scoped-readiness.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  — Accepted-source rebind must resolve exact source, affected consumers, schemas/rules and relevant semantic fields; interface agreement is planning only. **Граница:** Does not turn verification preparation into a global completion barrier or substitute for the named final execution receipt.
- [Workspace production loop and production-trigger proof owner](../../../../../../policy-engine/src/polisyos/runtime/quality/workspace/loop.py) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  — The canonical WorkspaceLoop has a real-CAS production-case path and distinguishes production evidence from fixture execution; the historical implementation describes its refusal-path limits. **Граница:** Source inspection and a route-shaped ProductionLoopRunProof do not prove an actual measurement-rooted outcome, persisted artifacts, or consumer readback.
- [Open Containers Initiative Image Specification: Descriptor](https://specs.opencontainers.org/image-spec/descriptor/) — A content consumer should verify referenced bytes against the descriptor digest and size. **Граница:** A digest binds bytes; by itself it does not establish semantic validity, correct provenance, a runtime environment, or authority.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="GYD-18"></a>

## GYD-18 — V3 per-domain multi-case distribution battery

Исходная запись: [tasks.json](../tasks.json), `tasks[id=GYD-18]`. Review: [root-review](root-review.md#GYD-18).

### Предпочтительное решение

Recompute the V3 distribution from the frozen, source-bound N10 corpus and its three acquisition-class runs, incorporating the required second domain, non-panel case, unseen third domain, and the post-N13b re-entry case at its true depth. Reuse V2 persisted outputs only where the input/case and source identities match. Report full per-domain distributions for terminal status, evidence kind, decision grade and rung with explicit denominators, preserving mixed results and uncertainty. Include local depth-1 and recursive/depth-2 behavior; for a concrete joint-design property accept the validated exact JOINT CompositionCertificate witness, not a pairwise substitute. Where recursion or evidence is inadequate, the valid terminal may be an honest typed limitation; do not require every domain to be useful or successful. Use the existing N10/N13b owner artifacts and the canonical CompositionCertificate owner after accepted-source rebind; do not fork the duplicated certificate owner into another corpus or verifier.

### Что переиспользовать

- `policy-engine/tools/quality/validation/check_layer3_gy_n10_cg1_l2_relation_census.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `N10 capstone relation census`. Existing frozen N10 corpus/artifact owner for the multi-case relation evidence.
- `policy-engine/tools/quality/validation/check_layer3_gy_n13b_acquisition_contract.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `N13b acquisition/re-entry contract`. Existing acquisition class and post-N13b re-entry evidence owner.
- `policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `§9 Phase 7 V3 criterion / canonical certificate decision`. Requires local and recursive coverage, multiple domains, distributions, N10/N13b runs, and exact joint or typed terminal evidence.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Freeze and bind the complete required case set, acquisition class, domain identity, run and source hashes; derive the denominator from the corpus owner, not the result table.
2. Join V2 output only for identical case/input/rule identities; execute only missing required cases or depth transitions under the existing permit.
3. Recompute each domain's status/evidence/grade/rung distribution and preserve empty/mixed strata explicitly; include the second, non-panel and unseen-third domain.
4. For recursive cases resolve the canonical certificate and exact JOINT witness when that is the tested property; otherwise retain the correct typed terminal/limitation.
5. Remove one corpus member in a controlled probe and confirm the denominator and resulting distribution change or become not_established.
6. For the specified post-N13b fixed re-entry witness, require typed_deeper_terminal and no world-growth epoch, as the original criterion states. This is not an arbitrary successful or limited terminal; preserve the separate branch/effect accounting.

### Рассмотренные альтернативы

- **Build a new universal benchmark or duplicate CompositionCertificate registry** — Duplicates N10/N13b and risks divergence from the canonical certificate owner.
- **Require pairwise evidence for every joint property or require a positive result in every domain** — Pairwise is not a substitute for an exact validated JOINT witness; universal success would erase honest plurality and typed terminals.
- **Report only pooled counts or a single average** — It can hide an unseen-domain or acquisition-class failure and violates per-domain distributions.

### Free-grow и ресурсы

- **data or config growth:** New cases/domains append through N10/N13b corpus owners with versioned labels and provenance; existing cases retain their historical corpus version.
- **extension boundary:** A new case class may need a typed acquisition/domain label and its own owner evidence; no arbitrary domain assertion becomes proof of coverage.
- **resource behavior:** Reuse exact V2 outputs, bound the recursive depth to the criterion's existing cases, and recompute summary distributions from all members. Missing strata stay visible as not_established; no invented sample-size threshold.


### Миграция и восстановление

Keep old reports pinned to their original corpus/source hashes. Corrected labels or denominator changes create a new readout that explains the delta; never overwrite a historical run or recast a failed/limited terminal as success.


### Композиция и owners

- Distributions preserve within-domain plurality and the original terminal/status lattice; there is no new global pass threshold.
- A concrete joint design property may use its exact validated JOINT witness; it does not imply every composition property is pairwise-checked.
- Corpus member removal must alter the recomputed denominator/readout; an unchanged declared summary is a P38 proxy.


### Acceptance и различающие проверки

- Positive: complete N10 acquisition runs plus the second domain, non-panel, unseen third, and post-N13b re-entry are represented at the required local/recursive depth.
- Adversarial: an unseen-third domain missing or mislabeled cannot be hidden by pooling; mixed evidence grades remain visible.
- Removal: deleting one bound case/member changes the denominator/readout or produces not_established; markers alone do not preserve a pass.
- The named post-N13b re-entry yields typed_deeper_terminal and zero world-growth epoch; replacing it with another terminal or advancing an epoch must fail this row even if pooled distributions remain unchanged.


### Входы и ответственность за их получение

- Accepted E02 corpus/schema, actual N10/N13b artifacts, canonical certificate owner identity, and permitted domain cases.


### Когда обоснованно отклониться

- If a required domain/case or acquisition class is unavailable, publish the observed distribution with the absent stratum explicitly not_established; do not infer a zero or success.
- If canonical CompositionCertificate ownership remains split after rebind, pause only the affected recursive proof for owner reconciliation; do not create another authority path.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [GY engine subordination plan, §9 Phase 7 verification criteria](../../../../../../policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` · #phase-7 — The original V1–V7 criteria, including V4 negatives a–v, define the evidence this proposal must preserve. **Граница:** Historical planning source; its implementation and product verification status remain planned_after_E02_acceptance and UNRUN in the assigned input. Rebind to the accepted E02 source before execution.
- [R9/GY/Atlas workstream 03, GY tasks](../../../../../../policy-engine/docs/plans/active/post-e02-r9-unified-implementation/workstreams/03-gy.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  — The workstream preserves task timing, formal status conflicts, final freeze/replay ordering, shared artifacts and no-duplicate-wave requirements. **Граница:** Planning evidence only; it cannot establish a product result or accepted tree.
- [Execution 07 scoped readiness and edge decisions](../../../../../../policy-engine/docs/plans/active/post-e02-r9-unified-implementation/execution/07-scoped-readiness.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  — Accepted-source rebind must resolve exact source, affected consumers, schemas/rules and relevant semantic fields; interface agreement is planning only. **Граница:** Does not turn verification preparation into a global completion barrier or substitute for the named final execution receipt.
- [Hypothesis Quickstart](https://hypothesis.readthedocs.io/en/latest/quickstart.html) — Property-based examples can be generated through ordinary Python test functions and run by pytest/unittest; example volume is configurable. **Граница:** Generated examples explore the supplied strategy and property; they do not establish oracle correctness, source-set completeness, or proof over all inputs.
- [Hypothesis stateful testing](https://hypothesis.readthedocs.io/en/latest/stateful.html) — Rule-based stateful tests generate action sequences, can compare an implementation with a reference model, and shrink failures to shorter sequences. **Граница:** The reference model and action language can omit the very transition that matters; sequence generation is not evidence that the model covers PolicyOS lifecycle semantics.
- [Metamorphic Testing: A New Approach for Generating Next Test Cases (HKUST-CS98-01)](https://www.cse.ust.hk/faculty/scc/publ/CS98-01-metamorphictesting.pdf) — Metamorphic testing derives follow-up test cases and expected relations from successful cases when a direct oracle is difficult to obtain. **Граница:** The chosen relation is itself a premise; relations must be reasoned from the original criterion and challenged with adversarial variants, not treated as self-validating.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="GYD-19"></a>

## GYD-19 — V4 live adversarial firewall battery

Исходная запись: [tasks.json](../tasks.json), `tasks[id=GYD-19]`. Review: [root-review](root-review.md#GYD-19).

### Предпочтительное решение

Keep the original V4 a–v list as the authoritative indexed matrix and exercise each negative at its actual consumer/owner boundary, with one persisted deciding witness per case. Expected outcomes must be derived from each original criterion and accepted source semantics; do not write a new generic firewall or classify rows as blanket “applicable only.” The matrix covers: (a) Ring2 field write rejected; (b) synthetic/no-measurement promotion rejected; (c) candidate/failed flow cannot surface/export/sign; (d) poor-recall abstention leads to search-ceiling repair; (e) feedback decomposition invalidates composition; (f) ungrounded emergent program claim is capped; (g) nested secret in raw artifact is redacted; (h) nested connector/DAG secret is redacted or blocked; (i) S12 authorial reference that cannot dereference is downgraded; (j) candidate-positive status cannot promote without the boundary; (k) CAS tamper is rejected/redigested; (l) time-role mismatch is blocked, downgraded or creates obligation; (m) optimistic authority transform loses to lower-A boundary and is traced; (n) VOI manipulation is rejected/clipped with audit; (o) failure cannot become clean completed job; (p) below-certified high surrogate cannot promote; (q) uncertified sample-only ValueOuterSet cannot mint promotion value; (r) simulate_only cannot shrink K_world; (s) stale certificate is removed/revalidation_required; (t) risk above δ is blocked; (u) field_pilot without EvalSafety is blocked; and (v) unsupported-equilibrium feedback is capped. Add malformed/synonym/forged variants only where they distinguish the same boundary, plus one sibling-consumer check for shared gates. Any genuine exclusion requires completed P34 isolation and competent source-bound disposition, and is not counted as a pass.

### Что переиспользовать

- `policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `§9 Phase 7 V4 original negative criteria a–v`. Original indexed negative list; must remain intact, including exclusions rule.
- `policy-engine/tools/quality/validation/check_policy_design_case_layer3_gx_hardening.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `existing GX hardening validation owner`. Reuse the actual consumer-side hardening paths applicable to GY artifacts after rebind; do not replace them with marker checks.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Bind each letter to its canonical consumer, original source predicate, precondition, expected typed refusal/limitation, and persisted deciding evidence; record the exact execution path and command before the final wave.
2. Retain all a–v rows; run every original negative after freeze. Add adversarial present-but-fake, malformed/synonym, stale-reference and sibling-consumer variants only where they challenge the same property.
3. Use targeted stateful sequences for lifecycle-sensitive transitions (candidate→promotion, stale→revalidation, failure→completion) and bounded property-based cases for value/schema edges; they supplement but do not replace original cases.
4. Run matched remove-property/keep-marker probes at representative semantic gates; where different owner mechanisms exist, probe each distinct mechanism. Preserve failure traces and owner attribution.
5. Record exclusions only after full P34 isolation and competent source-bound disposition; exclusion remains outside the passing count.

### Рассмотренные альтернативы

- **Replace a–v with a broad ‘firewall passed’ boolean** — Destroys original criterion traceability and allows a missing row or wrong consumer to be masked.
- **Run a large undirected mutation campaign** — Expensive and less interpretable than criterion-specific removals; one targeted causal mutation per semantic owner has stronger diagnostic value.
- **Use declared status strings as the expected outcome** — It would test the declaration instead of the authority/status property; bind the expected result to the original criterion and owner semantics.

### Free-grow и ресурсы

- **data or config growth:** New negative cases append as separately indexed cases only when authorized by the original obligation owner; existing a–v identities and historical results remain fixed.
- **extension boundary:** New authority boundary requires typed consumer evidence and composition semantics; no arbitrary rule list, keyword, or LLM interpretation becomes an authoritative oracle.
- **resource behavior:** Use small deterministic fixtures per owner, bounded generated edge cases, and a small targeted mutation set; serialize shared CAS/world fixtures and keep the single broad wave after freeze.


### Миграция и восстановление

If a test harness or criterion mapping changes, retain prior result IDs and reissue a new matrix version. Failed, skipped, and excluded cases stay distinct; no partial phase lift or status rewrite follows a red result.


### Композиция и owners

- Preserve each original a–v predicate; a case can fail, pass, or have an explicitly source-bound disposition, never disappear from the denominator.
- Mixed warning/partial/contested/review-required outcomes use existing status composition rules and do not silently become clean allow.
- Classify gate-premise provenance for each deciding predicate; fail closed where authority depends on a merely consumer-asserted or not-established predicate.


### Acceptance и различающие проверки

- Positive: the exact original violating inputs reach their real consumers and produce criterion-conforming refusal, redaction, cap, audit, or revalidation behavior.
- Adversarial: candidate-only, forged, stale, nested-secret, and sibling-consumer cases cannot bypass the same boundary.
- Removal: delete the protected semantic gate while preserving its marker/schema name; the relevant negative battery must fail.


### Входы и ответственность за их получение

- Accepted E02 owner routes and testable permitted fixtures for CAS, world simulation, policy time, VOI and EvalSafety boundaries.


### Когда обоснованно отклониться

- An unreachable original case remains open until full P34 isolation and source-bound competent disposition; do not skip it as inapplicable by assertion.
- A failed gate whose base ownership is uncertain requires exact base replay and denominator proof under P41 before labeling it inherited.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [GY engine subordination plan, §9 Phase 7 verification criteria](../../../../../../policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` · #phase-7 — The original V1–V7 criteria, including V4 negatives a–v, define the evidence this proposal must preserve. **Граница:** Historical planning source; its implementation and product verification status remain planned_after_E02_acceptance and UNRUN in the assigned input. Rebind to the accepted E02 source before execution.
- [R9/GY/Atlas workstream 03, GY tasks](../../../../../../policy-engine/docs/plans/active/post-e02-r9-unified-implementation/workstreams/03-gy.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  — The workstream preserves task timing, formal status conflicts, final freeze/replay ordering, shared artifacts and no-duplicate-wave requirements. **Граница:** Planning evidence only; it cannot establish a product result or accepted tree.
- [Execution 07 scoped readiness and edge decisions](../../../../../../policy-engine/docs/plans/active/post-e02-r9-unified-implementation/execution/07-scoped-readiness.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  — Accepted-source rebind must resolve exact source, affected consumers, schemas/rules and relevant semantic fields; interface agreement is planning only. **Граница:** Does not turn verification preparation into a global completion barrier or substitute for the named final execution receipt.
- [Hypothesis Quickstart](https://hypothesis.readthedocs.io/en/latest/quickstart.html) — Property-based examples can be generated through ordinary Python test functions and run by pytest/unittest; example volume is configurable. **Граница:** Generated examples explore the supplied strategy and property; they do not establish oracle correctness, source-set completeness, or proof over all inputs.
- [Hypothesis stateful testing](https://hypothesis.readthedocs.io/en/latest/stateful.html) — Rule-based stateful tests generate action sequences, can compare an implementation with a reference model, and shrink failures to shorter sequences. **Граница:** The reference model and action language can omit the very transition that matters; sequence generation is not evidence that the model covers PolicyOS lifecycle semantics.
- [Metamorphic Testing: A New Approach for Generating Next Test Cases (HKUST-CS98-01)](https://www.cse.ust.hk/faculty/scc/publ/CS98-01-metamorphictesting.pdf) — Metamorphic testing derives follow-up test cases and expected relations from successful cases when a direct oracle is difficult to obtain. **Граница:** The chosen relation is itself a premise; relations must be reasoned from the original criterion and challenged with adversarial variants, not treated as self-validating.
- [Toward Just-in-time and Language-agnostic Mutation Testing](https://labs.oracle.com/pls/apex/f?p=LABS%3A0%3A111432938371215%3AAPPLICATION_PROCESS%3DGETDOC_INLINE%3A%3A%3ADOC_ID%3A3081) — Mutation testing checks whether tests detect injected faults; full campaigns can be expensive, motivating focused and incremental mutants. **Граница:** A surviving or killed mutant speaks only to that mutation and test oracle; a small targeted set does not estimate all defect coverage.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="GYD-20"></a>

## GYD-20 — V5 three-level replay audit

Исходная запись: [tasks.json](../tasks.json), `tasks[id=GYD-20]`. Review: [root-review](root-review.md#GYD-20).

### Предпочтительное решение

Keep the three V5 levels separate and bind each to the same frozen source profile. For deterministic operations only, replay one representative criterion-bearing operation from V2 with identical input and parameter hashes, seed, code/rule/schema versions, container digest and relevant dependency/hardware profile, then compare the named output hash across distinct execution times. The OCI digest pattern supports verifying bytes, not semantic truth or full environment identity. For agentic work, reuse the persisted Research DAG replay owner to reconstruct the stored decision/provenance trace without calling a live provider; report trace reconstruction, not identical model output or fresh re-execution. At the promoted-artifact level, resolve and hash artifact bytes, walk provenance, then distinguish historical-rule validation from current-rule revalidation. Inspect `gy_evidence_canon` carefully: the observed helper strips `_at` and `_duration` suffixes, so do not claim time-invariant semantic identity until capture/occurrence timestamps are distinguished from effective/as-of/source times and the latter remain bound. A same-code rerun establishes consistency; independent verification is required only for a correctness claim that crosses the authority/content-bind boundary, not as a blanket second engine for every reducer.

### Что переиспользовать

- `policy-engine/src/polisyos/scientist/methods/research_dag/replay.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `plan_research_replay / replay_research_path / public_replay_export`. Can reconstruct persisted agentic trace without live calls; explicitly does not promise deterministic token or live-web replay.
- `policy-engine/tools/quality/validation/gy_evidence_canon.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `canonical_evidence_hash`. Existing canonical hash helper removes volatile fields, including broad suffix classes requiring semantic-time review.
- `policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `§9 Phase 7 V5 criterion`. Requires operation byte identity, agent trace reconstruction, artifact audit/revalidation, and time-invariant hashes as distinct levels.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Freeze exact operation/case/artifact identities and runtime profile; derive the deterministic/non-deterministic classification from the operation owner rather than assuming all tasks are deterministic.
2. Replay one V2-derived deterministic operation with matching content-bound inputs, params, seed, code/rule/schema and container/dependency profile; compare the exact named outputs and record any nondeterministic dependency boundary.
3. Reconstruct the stored agentic DAG and decision/provenance links offline with no live model/web call; label hidden/redacted content and unavailable providers accurately.
4. Resolve promoted artifact references from CAS and independently recompute byte digest/size; revalidate historical and current rules separately without rewriting the historical result.
5. Probe canonicalization with changed capture time (expected unchanged) and changed semantic source/effective/as-of time (expected changed digest or explicit revalidation).

### Рассмотренные альтернативы

- **Demand bit-identical re-execution of live LLM/provider or web decisions** — The native owner reconstructs trace without live calls; provider/model/platform variation makes exact re-execution a different and unsupported claim.
- **Hash only the container or use a floating tag** — A runtime digest does not bind input, params, data, rules, hardware or semantic validity; bind each required dimension explicitly.
- **Strip every timestamp-looking field from the canonical hash** — It can erase load-bearing time-role evidence and make a changed historical basis look invariant.

### Free-grow и ресурсы

- **data or config growth:** Add operation classes and replay cases through their existing owner with a deterministic/non-deterministic label and profile; artifact versions remain source-bound.
- **extension boundary:** A new replay guarantee requires an owner-defined determinism contract and versioned input surface; trace reconstruction cannot be upgraded into model re-execution by naming convention.
- **resource behavior:** One deterministic operation replay plus offline trace reconstruction and artifact walk; no duplicate full V2 loop or provider calls. Restrict byte identity to a fixed profile and fail with scoped limitation where determinism is unsupported.


### Миграция и восстановление

Never overwrite historical outputs. If canonicalization changes, issue a new hash/version and explain old/new semantics. Preserve current and historical revalidation results separately; a failed replay is evidence, not a reason to delete an artifact.


### Композиция и owners

- Deterministic operation replay, agent trace reconstruction, and promoted-artifact revalidation are separate claims and evidence paths.
- Capture-time changes may be ignored only if semantic time fields remain hashed or separately bound; rule/schema version and provenance stay in the verification context.
- Content digest proves byte equality only; semantic/authority validity is supplied by the relevant bound verifier.


### Acceptance и различающие проверки

- Positive: one named deterministic operation repeats byte-identically under an identical pinned profile; the stored agent trace reconstructs without live calls; promoted artifacts resolve and pass historical/current validation as recorded.
- Adversarial: profile, input, seed, rule version or semantic time changes are exposed and cannot be presented as the same replay basis.
- Removal: remove a replay binding/corpus member or perturb semantic time while preserving capture-time markers; the hash/receipt changes or result becomes not_established.


### Входы и ответственность за их получение

- Accepted E02 operation classification, V2 persisted inputs/artifacts, replay profile/container/dependency digests, and historical/current rule versions.


### Когда обоснованно отклониться

- If an operation is provider-, platform-, or hardware-nondeterministic, downgrade that level to trace reconstruction or scoped consistency and say why; do not force byte equality.
- If the current canonicalizer removes semantic times, V5 time-invariance is not established until owner-level correction and revalidation are reviewed.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [GY engine subordination plan, §9 Phase 7 verification criteria](../../../../../../policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` · #phase-7 — The original V1–V7 criteria, including V4 negatives a–v, define the evidence this proposal must preserve. **Граница:** Historical planning source; its implementation and product verification status remain planned_after_E02_acceptance and UNRUN in the assigned input. Rebind to the accepted E02 source before execution.
- [R9/GY/Atlas workstream 03, GY tasks](../../../../../../policy-engine/docs/plans/active/post-e02-r9-unified-implementation/workstreams/03-gy.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  — The workstream preserves task timing, formal status conflicts, final freeze/replay ordering, shared artifacts and no-duplicate-wave requirements. **Граница:** Planning evidence only; it cannot establish a product result or accepted tree.
- [Execution 07 scoped readiness and edge decisions](../../../../../../policy-engine/docs/plans/active/post-e02-r9-unified-implementation/execution/07-scoped-readiness.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  — Accepted-source rebind must resolve exact source, affected consumers, schemas/rules and relevant semantic fields; interface agreement is planning only. **Граница:** Does not turn verification preparation into a global completion barrier or substitute for the named final execution receipt.
- [Research DAG replay owner](../../../../../../policy-engine/src/polisyos/scientist/methods/research_dag/replay.py) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  — The current owner can reconstruct a persisted high-level agentic decision/provenance trace without making new live calls. **Граница:** Trace reconstruction is not deterministic provider re-execution, byte-identical output replay, or promoted-artifact revalidation.
- [GY evidence canonical hash helper](../../../../../../policy-engine/tools/quality/validation/gy_evidence_canon.py) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  — A native canonical evidence hash helper exists and removes selected volatile values before hashing. **Граница:** At the historical observation it also strips keys ending in _at and _duration; this is not safe evidence that authority-relevant effective/as-of/source times are preserved in the digest.
- [Open Containers Initiative Image Specification: Descriptor](https://specs.opencontainers.org/image-spec/descriptor/) — A content consumer should verify referenced bytes against the descriptor digest and size. **Граница:** A digest binds bytes; by itself it does not establish semantic validity, correct provenance, a runtime environment, or authority.
- [PyTorch reproducibility notes](https://docs.pytorch.org/docs/stable/notes/randomness.html) — Reproducibility is scoped to software/hardware conditions; deterministic choices may be slower or unavailable, and cross-release/platform bit identity is not a general promise. **Граница:** This documents PyTorch-specific behavior, not the PolicyOS runtime; use it to scope replay claims, not as evidence that local operations are nondeterministic or slow.
- [SOURCE_DATE_EPOCH reproducible-builds documentation](https://reproducible-builds.org/docs/source-date-epoch/) — Normalizing build timestamps can remove one source of build variation. **Граница:** Controlling one timestamp does not establish whole-program, model, data, hardware, or semantic reproducibility.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="GYD-21"></a>

## GYD-21 — V6 whole GX/Task-0/audit validation closure

Исходная запись: [tasks.json](../tasks.json), `tasks[id=GYD-21]`. Review: [root-review](root-review.md#GYD-21).

### Предпочтительное решение

Prepare a single final validation wave over the exact frozen GY artifact family using the existing GX hardening validators, Task-0 coverage matrix, 16 audit validators, and GY-V validators. Derive the complete artifact and validator denominators from their canonical owners; invoke each real validator against actual resolved artifacts, preserving unique owner outputs and mapping which artifacts each validator consumes. This is a bounded closure of the stated validator set, not “every test in the repository” and not a new parallel validator registry. A validator counts only if it recomputes its protected property from source-of-truth objects and fails on a property-removal/corruption probe; names, field presence, paths and exit codes alone are markers. Include an omitted-artifact drift check and a representative property-specific remove-the-property-keep-markers probe for each distinct mechanism. Coordinate the full wave with root’s final closeout so the deciding outputs are retained once. If any artifact has no real consuming verifier, report its precise capability gap instead of silently calling V6 complete. The expected artifact×validator applicability relation is derived first from original V6 criteria and native validator-owner contracts, independently of observed invocations; compare expected pairs with actual consumed pairs. Source-supported not_applicable is explicit and may not be inferred from missing execution.

### Что переиспользовать

- `policy-engine/tools/quality/validation/check_policy_design_case_layer3_gx_hardening.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `GX hardening validator owner`. Existing cross-cutting validation owner for GY artifacts in the GX scope.
- `policy-engine/tools/quality/validation/check_layer3_gy_capability_coverage_matrix.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `GY coverage matrix validation`. Existing Task-0/capability coverage anchor; pair with V1's complete denominator proof.
- `policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `§9 Phase 7 V6 criterion`. Sets the scoped validator family and no-uncatalogued-drift completion property.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. After E02 rebind, inventory the complete GY artifact family and existing validator owners from canonical plans/source; bind versions, inputs and consumers. Do not create a substitute registry.
2. Derive expected artifact×validator applicability pairs independently from original requirements and native schema/property contracts before reading actual invocation records. Compare expected pairs to actual resolved inputs; actual consumers cannot declare away a missing applicability edge.
3. For every validator, identify its actual object inputs and semantic property; run its owner command once in the final frozen wave and retain the complete deciding output.
4. Join artifact denominator to validators actually consuming each artifact; run omitted-artifact drift and targeted corruption/removal probes for each distinct owner mechanism.
5. Read validator results and public/generated companions from source-bound locations; report red/unknown rows and exact capability labels if a consumer or verifier is absent.

### Рассмотренные альтернативы

- **Create one new mega-validator that reimplements all checks** — Duplicates semantic owners, weakens diagnostics and risks drift from native validators.
- **Run all repository tests and equate green with GY closure** — It can miss artifacts that no test consumes and adds broad compute without proving the specified validator/artifact relation.
- **Accept validator names/markers or exit status only** — P29/P38 require actual path execution and property behavior; a property can be removed while markers remain.

### Free-grow и ресурсы

- **data or config growth:** New artifacts enter through their native owner/schema and the canonical artifact-family inventory; the existing validator set expands only when the accepted source adds an applicable owner/property.
- **extension boundary:** New validator semantics belong to the relevant owner and must consume real artifacts; V6 reports closure rather than authorizing arbitrary verifier plugins.
- **resource behavior:** One consolidated final wave, one output per unique owner, and bounded property probes; no duplicate full replay. Oversized raw evidence stays in ignored raw storage and receipts cite path plus hash.


### Миграция и восстановление

Keep historical validator outputs and prior artifact versions immutable. If one validator fails or misses an artifact, retain its red result and owner; do not waive it or rewrite formal Phase 5/6 status. Re-run only after a material fix or final freeze changes the deciding input.


### Композиция и owners

- No uncatalogued drift means complete source-derived artifact denominator joined to actual consumer/verifier coverage, not merely all known commands green.
- Each gate predicate's provenance is classified at admission under P37; missing or merely consumer-asserted authority predicates remain fail-closed.
- The broad final wave is a task-specific completion receipt, not a new global barrier for unrelated preparation or reconciled scopes.


### Acceptance и различающие проверки

- Positive: every required GY artifact is consumed by its applicable real validator family and all recomputed properties hold on the frozen source.
- Adversarial: one corrupt field and one omitted artifact produce a failing or explicitly not_established owner result.
- Removal: remove a protected property while retaining validator/matrix markers; its semantic validator fails.
- Remove one required validator/artifact edge while leaving the artifact covered by another validator; pair-level completeness must fail. Artifact coverage alone is insufficient.


### Входы и ответственность за их получение

- Accepted E02 artifact family, exact validator versions/commands, Task-0 and 16-audit scope, and formal Phase 5/6 reconciliation.


### Когда обоснованно отклониться

- If artifact-to-validator mapping is incomplete, stop only the affected V6 closure and report consumer_missing/verification_missing/surface_missing precisely.
- If a final review lands after the freeze, reprice and rerun only the affected deciding gates; do not duplicate unrelated full waves.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [GY engine subordination plan, §9 Phase 7 verification criteria](../../../../../../policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` · #phase-7 — The original V1–V7 criteria, including V4 negatives a–v, define the evidence this proposal must preserve. **Граница:** Historical planning source; its implementation and product verification status remain planned_after_E02_acceptance and UNRUN in the assigned input. Rebind to the accepted E02 source before execution.
- [R9/GY/Atlas workstream 03, GY tasks](../../../../../../policy-engine/docs/plans/active/post-e02-r9-unified-implementation/workstreams/03-gy.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  — The workstream preserves task timing, formal status conflicts, final freeze/replay ordering, shared artifacts and no-duplicate-wave requirements. **Граница:** Planning evidence only; it cannot establish a product result or accepted tree.
- [Execution 07 scoped readiness and edge decisions](../../../../../../policy-engine/docs/plans/active/post-e02-r9-unified-implementation/execution/07-scoped-readiness.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  — Accepted-source rebind must resolve exact source, affected consumers, schemas/rules and relevant semantic fields; interface agreement is planning only. **Граница:** Does not turn verification preparation into a global completion barrier or substitute for the named final execution receipt.
- [GY capability coverage matrix checker](../../../../../../policy-engine/tools/quality/validation/check_layer3_gy_capability_coverage_matrix.py) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  — A native matrix checker exists and can be extended at its current ownership boundary. **Граница:** At the historical observation it validates declared matrix content and derived summaries; it does not itself establish the complete moved-row denominator or that each declared capability is behaviorally present and consumed.
- [Toward Just-in-time and Language-agnostic Mutation Testing](https://labs.oracle.com/pls/apex/f?p=LABS%3A0%3A111432938371215%3AAPPLICATION_PROCESS%3DGETDOC_INLINE%3A%3A%3ADOC_ID%3A3081) — Mutation testing checks whether tests detect injected faults; full campaigns can be expensive, motivating focused and incremental mutants. **Граница:** A surviving or killed mutant speaks only to that mutation and test oracle; a small targeted set does not estimate all defect coverage.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="GYD-22"></a>

## GYD-22 — V7 five health-signal readout

Исходная запись: [tasks.json](../tasks.json), `tasks[id=GYD-22]`. Review: [root-review](root-review.md#GYD-22).

### Предпочтительное решение

Reuse the existing G8 health-metric governance owner and Cycle Board surface for the five constitution signals: envelope expansion (T1), semantic loss (T2), governance throughput (T3), demand-pull/abstention (T6), and search recall/index staleness (T7). Pull values and source snapshots from V2/V3 persisted runs and the metrics' canonical owners; report full denominators, source/version hashes, missingness and cross-metric diagnosis. Preserve the G8 distinction between domain-ceiling and search-ceiling: known-seed recall misses or stale canonical index prevent a no-hit result from being read as evidence of no mandate. A missing signal source is missing/not_established, not zero. These are diagnostic/descriptive signals and must not be optimized toward an invented useful-rate or promoted to causal effects. A causal attribution between a search ceiling and a domain ceiling needs a predeclared, same-frozen-case contrast and explicit identifying assumptions; otherwise label the interpretation as diagnostic classification or unknown. Use fully named metrics because Atlas's unrelated T1/T6/T7 tension IDs are distinct from these constitution metric IDs.

### Что переиспользовать

- `policy-engine/src/polisyos/runtime/quality/proving_ground/health_metric_governance.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `G8 canonical metric registry, source snapshots, trend and cross-metric diagnosis`. Existing owner has five canonical metrics/aliases, domain-vs-search ceiling logic, and anti-gaming rules.
- `policy-engine/src/polisyos/runtime/quality/README.md@dccea950845cda5b38f026e7770c07819d31f4d9` — `G8/GY metric ownership map`. Explains G8 metric governance and upstream GY source owners.
- `policy-engine/architecture/policy_design_case/layer3_health_metric_ledgers.toml@dccea950845cda5b38f026e7770c07819d31f4d9` — `existing health metric ledger definitions`. Existing metric delta/ledger artifact family; no new parallel registry is needed.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. After accepted rebind, map each fully named signal to its canonical source owner, definition, time window and denominator; resolve the T1/T6/T7 naming collision in the readout labels.
2. Consume the same frozen V2/V3 run and existing metric source snapshots; compute/read all five signals through G8 and its current Cycle Board consumer.
3. Report values, denominators, missingness, source hashes, uncertainty and G8 cross-metric diagnosis; do not smooth missing into zero or invent thresholds.
4. Exercise search-recall and index-staleness guard with a known-seed miss and a stale-index case; report domain/search explanation only to the extent the existing gate supports it.
5. If a causal claim is requested, define a same-case, predeclared contrast and assumptions before inspecting outcomes; otherwise keep the claim descriptive.

### Рассмотренные альтернативы

- **Create a new five-metric registry or dashboard** — G8, the metric ledgers and Cycle Board already own the definitions and surface; a parallel owner invites semantic drift.
- **Set targets for useful-design rate or treat health deltas as outcomes to optimize** — Would incentivize gaming and violate the existing G8 restriction on causal-effect/useful-design authority.
- **Infer causal search-vs-domain explanations from correlated metric movement** — Descriptive cross-metric diagnoses do not identify the counterfactual; missing controlled contrast means causal effect is not established.

### Free-grow и ресурсы

- **data or config growth:** New observations append through canonical T1/T2/T3/T6/T7 source owners and G8 snapshots; definitions and aliases remain single-owner.
- **extension boundary:** A new signal requires owner-defined measure, denominator, time semantics, anti-gaming interpretation and consumer mapping; adding a label alone does not create a signal.
- **resource behavior:** Read the existing V2/V3 evidence and G8 snapshots once; no duplicate case wave or new instrumentation collection. Missing or stale source yields visible missingness and no ceiling conclusion.


### Миграция и восстановление

Preserve prior metric definitions and readouts by version. A corrected source/denominator creates a revised period with delta and provenance, not rewritten history. Remove only a faulty projection if needed; retain source records and uncertainty.


### Композиция и owners

- Metric plurality and mixed outcomes remain descriptive; no new global health pass/fail threshold is introduced.
- Domain/search-ceiling distinction is supported only when known-seed recall and index-freshness evidence are present; otherwise classification is not_established.
- Causal attribution requires an identified comparison; observation and cross-metric correlation alone do not establish effect.


### Acceptance и различающие проверки

- Positive: all five named signals have canonical definitions, source snapshots, denominator/time bounds, and a readable current G8/Cycle Board projection.
- Adversarial: missing a signal source is shown as missing/not_established, never zero; stale index or known-seed misses block a no-mandate interpretation.
- Removal: remove one source measurement and verify the result changes to missing/not_established; no inferred causal effect survives without a declared contrast.


### Входы и ответственность за их получение

- Accepted E02 metric source definitions, V2/V3 real run evidence, canonical known-seed corpus, index freshness evidence, and metric owner snapshots.


### Когда обоснованно отклониться

- If a named source is unavailable, publish partial plurality and identify the missing owner; do not synthesize a value.
- If interpreting a ceiling requires an unowned causal comparison, record the question as unresolved research and do not turn it into a code contract.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [GY engine subordination plan, §9 Phase 7 verification criteria](../../../../../../policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` · #phase-7 — The original V1–V7 criteria, including V4 negatives a–v, define the evidence this proposal must preserve. **Граница:** Historical planning source; its implementation and product verification status remain planned_after_E02_acceptance and UNRUN in the assigned input. Rebind to the accepted E02 source before execution.
- [R9/GY/Atlas workstream 03, GY tasks](../../../../../../policy-engine/docs/plans/active/post-e02-r9-unified-implementation/workstreams/03-gy.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  — The workstream preserves task timing, formal status conflicts, final freeze/replay ordering, shared artifacts and no-duplicate-wave requirements. **Граница:** Planning evidence only; it cannot establish a product result or accepted tree.
- [Execution 07 scoped readiness and edge decisions](../../../../../../policy-engine/docs/plans/active/post-e02-r9-unified-implementation/execution/07-scoped-readiness.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  — Accepted-source rebind must resolve exact source, affected consumers, schemas/rules and relevant semantic fields; interface agreement is planning only. **Граница:** Does not turn verification preparation into a global completion barrier or substitute for the named final execution receipt.
- [Health metric governance owner (G8)](../../../../../../policy-engine/src/polisyos/runtime/quality/proving_ground/health_metric_governance.py) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  — One existing owner normalizes health metric aliases, captures source snapshots, emits trend/cross-metric diagnoses, and distinguishes domain from search ceiling with anti-gaming checks; Cycle Board is an existing surface. **Граница:** This is a diagnostic metric governance owner, not causal identification or authority for useful-design-rate optimization.
- [Estimating Causal Effects of Treatments in Randomized and Nonrandomized Studies](https://dash.harvard.edu/entities/publication/73120378-82c0-6bd4-e053-0100007fdf3b) — Causal effect estimation requires controlled comparisons and explicit assumptions; randomization is useful where possible, with careful nonrandomized designs sometimes necessary. **Граница:** A descriptive health-signal dashboard or cross-metric association is not itself an identified causal effect.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.
