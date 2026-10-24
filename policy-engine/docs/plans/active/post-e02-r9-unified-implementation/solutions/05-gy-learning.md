# Диагностика, обучение и authority: предпочтительные решения

Статус: engineering recommendations; product execution UNRUN. Реализация только после E02 acceptance и полного affected-scope rebind. Исходные критерии не сокращаются; [общие решения](00-shared-decisions.md) предотвращают второго owner. [Нормативные уточнения](decision-clarifications.md) остаются предложениями.

<a id="GYD-08"></a>

## GYD-08 — AS2 sealed diagnosis holdout

Исходная запись: [tasks.json](../tasks.json), `tasks[id=GYD-08]`. Review: [root-review](root-review.md#GYD-08).

### Предпочтительное решение

Add one owner-local, sealed AS2 corpus and oracle under the runtime/quality diagnosis owner after that exact module is appointed. Freeze corpus/version, source-qualified adjudication provenance, diagnosis rule, selected risk-coverage estimand, and operating point before opening the oracle. Where the evidence admits competing causal completions, retain that uncertainty in the reference labels instead of forcing one cause. Include the all-unresolved baseline and original OPS-R7 version, interference, and repeated-look cases. The deliverable is a scoped audit report, not a numeric product threshold or population-level guarantee.

### Что переиспользовать

- `policy-engine/src/polisyos/runtime/quality/vocabulary_crosswalk.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `MovementClass`. Canonical candidate movement vocabulary includes prediction_error, observation_process_change, behavioral_response, context_or_interference, and diagnosis_unresolved; it is not a holdout owner.
- `policy-engine/docs/plans/active/post-e02-r9-unified-implementation/inventory/gy-inventory.json@dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` — `GY-AS2`. Source task assigns runtime/quality but the exact diagnosis/holdout module is not allocated at C.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. At rebind, appoint the existing diagnosis evidence owner and freeze a content-addressed corpus manifest, oracle custodian, blind access path, and classifier/rule version.
2. Pre-register the risk-coverage calculation and operating point from training/calibration inputs; never tune them on sealed outcomes. Keep the all-unresolved baseline and any source-supported competing labels as reference behaviors.
3. Run one sealed comparison with provenance-bound cause adjudications and OPS-R7 adversarial cases; emit the audit receipt with input, rule, and time refs, then let O1 resolve and verify it. Preserve disagreement/uncertainty rather than converting it to a single authoritative cause.
4. Prepare the concrete AS2 operational clarification in decision-clarifications.md for the criterion owner before claiming its ambiguous comparator satisfied. Continue the sealed-corpus, access-history and refusal implementation independently; preserve the original criterion until approval.

### Рассмотренные альтернативы

- **Expose a reusable holdout score during classifier development** — Adaptive feedback itself can leak the holdout; a reusable-holdout construction needs a separately designed validation interface and privacy/stability budget that this task has not adopted.
- **Use a time-uniform confidence sequence to bless all repeated looks** — That addresses optional stopping under a fixed process, not adaptive classifier/threshold selection or changing diagnosis targets.

### Free-grow и ресурсы

- **data or config growth:** Add labeled cases and rule versions as append-only corpus releases; keep the same predeclared risk-coverage semantics. A correctly added resource in an existing supported semantic/protocol class is discovered through the canonical corpus with zero new central code; new semantics require typed owner extension and conformance.
- **extension boundary:** A new cause class or scoring semantics needs typed mapping and oracle review under the canonical diagnosis owner; new wording alone cannot become an authority label.
- **resource behavior:** Pin corpus version and access budget per audit. Missing custodian, oracle, version, or capacity means no O1 admission; do not silently shorten the denominator or publish numeric WP-09/WP-10 thresholds.


### Миграция и восстановление

No existing diagnosis score is upgraded by proximity. A changed corpus or rule creates a new version and rerun; prior receipts remain replayable. Until AS2 admits, O1 emits no posterior update.


### Композиция и owners

- Seal report -> O1 evidence intake; O1 resolves the content-bound custodian result and frozen corpus/rule/run provenance. Protected oracle labels remain behind the blind evaluation boundary; do not leak them to the tuning/requesting process to satisfy a generic readback instruction.
- P37: resolve oracle membership, custody/access history, and label provenance to their source; use `independently_reconciled` only for an actual independent-correctness/blindness claim, since a same-owner rebuild proves consistency only. Candidate-selected thresholds remain `consumer_asserted` and cannot turn the gate green.
- P38: the property is blindness to holdout outcomes; a local seal/hash checks internal consistency only. A post-hoc threshold followed by resealing is a divergent case and must still fail admission.


### Acceptance и различающие проверки

- Positive: the predeclared design beats the all-unresolved baseline on the approved sealed risk/coverage measure. The original holdout-tuned comparator remains a separate unclosed criterion pending the precise operational clarification in decision-clarifications.md; neither a better raw score nor a clean label substitutes for admitted evaluation.
- Negative: leakage, post-hoc threshold, repeated-look, forced-coverage, wrong-version, and missing-oracle fixtures refuse O1 admission; removing the sealed oracle makes the same O1 consumer refuse.
- No WP-09/WP-10 number becomes a public or default threshold; the report preserves the tested denominator and limitation.
- The holdout-tuned challenge is the source-defined falsifier of the sealed evaluation protocol, not a universal theorem that every tuned classifier has a lower numeric score. Fix the exact comparator, access history and predeclared criterion before outcomes are seen; unresolved ambiguity returns to its source owner without weakening the original obligation.


### Входы и ответственность за их получение

- Source-qualified diagnosis adjudications, including disagreement/competing labels and provenance; claim independent correctness only when an independent validation basis is actually supplied.
- Exact deployment/intervention version, observation process, context/interference refs, and actuals that distinguish the cause classes.


### Когда обоснованно отклониться

- If required oracle custody/access boundaries or source-qualified labels cannot be established, retain diagnosis_unresolved and do not unlock O1; do not require an independent evaluator for a consistency-only rebuild.
- If repeated-look behavior is intended to be supported, record a separate method decision and assumptions before changing the fixture from a required failure.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [Generalization in Adaptive Data Analysis and Holdout Reuse](https://papers.nips.cc/paper/5993-generalization-in-adaptive-data-analysis-and-holdout-reuse.pdf) — Adaptive reuse of a holdout can overfit to that holdout; their reusable-holdout construction controls this through a restricted validation interface and privacy/stability arguments. **Граница:** This does not make a sealed file or checksum a privacy mechanism. PolicyOS has no adopted query budget or privacy guarantee here, so use this as the reason to protect AS2 and reject post-hoc tuning, not as a transferred guarantee.
- [Time-uniform, nonparametric, nonasymptotic confidence sequences](https://doi.org/10.1214/20-AOS1991) — Confidence sequences can give time-uniform coverage over an unbounded horizon under their stated stochastic conditions, including validity at arbitrary stopping times. **Граница:** A sequential interval does not cure holdout leakage, post-hoc outcome selection, cause misclassification, or context transport. GYD-08 asks for repeated-look failure fixtures, not adoption of a new sequential guarantee.
- [Adopted reading clarification: competing causal completions and claim-type-specific grounds](../../../../../../policy-engine/docs/system-design-decisions/policy-design-causal-operating-system-north-star.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  (§10, SDD-B01) — A singular world-model reference may be credal/set-valued and admit competing causal completions. Grounding is claim-type-specific: causal claims need causal grounds, measurement claims need construct/method grounds, and value claims need a declared frame and applicable mandate. **Граница:** This adopted target clarification does not certify implementation or impose a unique causal structure; actual admission still needs the relevant owner, evidence, and scope.
- [Stage 0 custody kernel K14 scope amendment](../../../../../../policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  (§4.2, S0-K14) — Independence is required for verification claims, including benchmark-oracle claims and assertions of independent validation. A same-code rebuild is permitted and establishes consistency, not correctness. **Граница:** Do not impose a separately owned evaluator on every ordinary rebuild; independence remains necessary when the claimed property or explicit verification claim requires it.
- [Universal design system Rule 12: corpus discovery and conforming resource growth](../../../../../../policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  (§4.3, Rule 12) — Capability is discovered by bounded search over the corpus rather than a hand-maintained central enumeration; a correctly added resource conforming to an existing semantic/protocol class is usable with zero new central code. **Граница:** A genuinely new transport or semantic capability still needs a typed native extension and conformance; search completeness and capacity remain governed and evidenced.
- [Withheld propositions: WP-01/02/03 and activation boundaries](../../../../../../policy-engine/docs/system-design-decisions/withheld-propositions-register.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  — WP-01 retains no posterior mutation pending its live producers and activation; WP-02 supplies no approved routine schedule. **Граница:** This recommendation does not change or activate a withheld proposition. Reconcile later ratification at accepted-source rebind.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="GYD-09"></a>

## GYD-09 — O1 confirmatory effect updater

Исходная запись: [tasks.json](../tasks.json), `tasks[id=GYD-09]`. Review: [root-review](root-review.md#GYD-09).

### Предпочтительное решение

Prepare the existing Scientist feedback owner for the requested typed Bayesian effect-posterior profile, while enforcing the current WP-01/WP-02 interim rule: no posterior mutation. C02 permits qualified inference plurality but does not activate an update policy. Build the live measurement/diagnosis, content-bound realized-versus-predicted comparison, W4-K02 provenance, W5-K03 ancestry/context/interference/observation/mechanism checks and consumed refusal path. Present their concrete evidence to the competent principal for the WP-01 activation decision; routine expected_variation assimilation additionally requires the WP-02/R4-Q01 ruling. Only after the actual activation record is reconciled may the selected updater produce a versioned operative effect update for O3. Isolated estimator research is a non-authoritative experiment in separate scratch, never a posterior attached to the operative effect/claim/world. No update policy is inferred from AS2 admission, a vocabulary ruling, successful tests or this recommendation.

### Что переиспользовать

- `policy-engine/src/polisyos/scientist/feedback/core.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `DecisionFeedbackService.evaluate_packet`. Loads actuals and compares monitoring ranges; it is a monitoring/reissue service, not a deployed-effect posterior writer.
- `policy-engine/src/polisyos/foundry/methods/catalog/bayesian/variational.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `MeanFieldVIEstimator; BBVIEstimator`. Existing Bayesian estimators are reusable for supported typed carriers; unhandled types must refuse honestly.
- `policy-engine/src/polisyos/runtime/quality/vocabulary_crosswalk.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `MovementClass`. GY-VC1 executed movement vocabulary; do not add a parallel cause taxonomy.
- `policy-engine/src/polisyos/runtime/quality/design_axes/post_deploy_accountability.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `DivergenceRecord`. Existing attributed divergence includes cause owner, evidence/time refs, learning eligibility, and the rule that implementation failure alone cannot refute policy theory.
- `policy-engine/src/polisyos/runtime/quality/world_model_record.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `persist_world_model_record; load_world_model_record`. Canonical WMR persistence/readback exists; GYD-09 should emit a posterior ref for O3 rather than create a second world writer.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Read the current WP-01/02/03 register and later ratification records at accepted-source rebind. Preserve the actual operative rule; a register entry alone is not activation.
2. Wire actuals, intervention/version ancestry, comparison, measurement validity, context/interference and mechanism contributors through the existing feedback owner. Resolve W4-K02 provenance and exact rule/input identities; retain set-valued or unresolved causes.
3. Implement and exercise the no-posterior-mutation refusal path and the activation-decision consumer. Prepare a concrete activation packet with live SMDV-1/comparison/provenance witnesses and failures; do not invent a second movement vocabulary.
4. After a competent scoped WP-01 activation, implement the selected Bayesian profile and immutable prior/model/estimator/uncertainty references with fresh O3/DS21 readers. A WP-02 routine schedule remains absent unless separately adopted. Keep each other inference profile and guarantee distinct.

### Рассмотренные альтернативы

- **Treat DecisionFeedbackService's confirm-range verdict as effect confirmation** — It measures movement against a monitoring contract but does not distinguish implementation, measurement, behavioral, interference, or policy-effect causes.
- **Add a standalone updater module and directly mutate the current WMR** — That creates a second owner/writer beside the feedback and WMR owners; a new file is only justified if owner review finds no suitable extension point, and branch mutation is assigned to O3.

### Free-grow и ресурсы

- **data or config growth:** Support additional typed effect/outcome carriers through the existing estimator and movement vocabulary with versioned rules.
- **extension boundary:** A new effect family needs a declared comparison mapping, uncertainty semantics, and typed owner review. A new inference profile is a separate qualified native extension with its own assumptions and consumer bridge; do not silently replace or mix the task’s Bayesian posterior semantics, and never coerce unsupported outcomes to a scalar.
- **resource behavior:** Posterior artifacts are immutable and append-only. If observation power, currentness, or supported estimator inputs are insufficient, preserve evidence and emit a typed limited/refused result without posterior mutation.


### Миграция и восстановление

Pre-activation and unresolved diagnosis leave the operative posterior unchanged. Activation is a versioned, scoped policy event, not migration by default. Preserve historical refusals. After authorized activation, corrections append supersession through the existing owner; only O3 may grow the world. A rollback cannot revive a withdrawn update policy or erase an erroneous historical update.


### Композиция и owners

- Current comparison/diagnosis/provenance -> refusal with no posterior mutation -> fresh feedback/O3/audit reader. Activation packet is a proposal consumed only after the competent decision.
- Activated exact update-policy ref + admitted AS2/W5-K03 inputs + qualified estimator -> immutable update -> O3. Absence or wrong scope/version of activation refuses; numeric posterior is not authority.
- C02 profile plurality preserves posterior/coverage/identified-set/procedural guarantees separately. K14 independence applies to an independent correctness claim, not every internal consistency rebuild.


### Acceptance и различающие проверки

- Current positive: real comparison/diagnosis traverses the producer and fresh consumer and correctly refuses posterior mutation under the interim rule; this proves the interim mechanism, not completion of the future update capability.
- Activation-dependent positive: after an actual competent activation record, exact eligible inputs produce the selected immutable update and O3 reads it; until then this positive is UNRUN/unavailable by ratified policy, not silently replaced by the refusal.
- Adversarial/removal: complete causal inputs plus absent/forged/wrong-version activation still produce no mutation. Removing the activation consumer while keeping flags must make the refusal control fail. Unresolved contributors never default to prediction_error.


### Входы и ответственность за их получение

- Real post-deployment actuals from the named measurement process.
- Source evidence for intervention/version ancestry and W5-K03 context, interference, observation validity, and mechanism; method-specific assumptions/inputs for whichever qualified inference profile is selected.
- Internal producers/comparison/provenance are assigned engineering; a competent WP-01 activation decision and, only if proposed, WP-02/R4-Q01 routine-policy ruling are genuine governance inputs. See decision-clarifications.md.


### Когда обоснованно отклониться

- If actual evidence supports only implementation or measurement change, retain the appropriate non-effect route and freeze the posterior.
- If an outcome has no owner-approved Bayesian estimator/uncertainty mapping, mark it limited/refused and propose typed owner review; do not relabel the posterior as coverage, an identified set, or another profile guarantee.
- A later ratified activation supersedes the interim constraint only for its exact scope; a source code path or author receipt does not.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [Transportability of Causal and Statistical Relations: A Formal Approach](https://ojs.aaai.org/index.php/AAAI/article/view/7861) — Selection diagrams make differences and commonalities between source and target environments explicit and support deciding whether a causal effect is identifiable in the target from available source experiments and target observations. **Граница:** This does not license automatic generalization to a new population, time, or interference regime. It depends on a causal graph and evidence for its selection assumptions.
- [Adopted reading clarification: competing causal completions and claim-type-specific grounds](../../../../../../policy-engine/docs/system-design-decisions/policy-design-causal-operating-system-north-star.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  (§10, SDD-B01) — A singular world-model reference may be credal/set-valued and admit competing causal completions. Grounding is claim-type-specific: causal claims need causal grounds, measurement claims need construct/method grounds, and value claims need a declared frame and applicable mandate. **Граница:** This adopted target clarification does not certify implementation or impose a unique causal structure; actual admission still needs the relevant owner, evidence, and scope.
- [Adopted target extension: inference plurality](../../../../../../policy-engine/docs/system-design-decisions/policy-design-causal-operating-system-north-star.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  (§10, SDD-C02) — Bayesian confirmatory updates remain supported, while explicitly justified frequentist, sequential, robust, or partial-identification profiles are also permitted for the propositions they support. Posterior probability, coverage, identification sets, and procedural no-number claims must not be silently mixed. **Граница:** C02 appoints no method owner, authorizes no posterior mutation, and does not transfer any method guarantee without its own assumptions and bridge.
- [Stage 0 custody kernel K14 scope amendment](../../../../../../policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  (§4.2, S0-K14) — Independence is required for verification claims, including benchmark-oracle claims and assertions of independent validation. A same-code rebuild is permitted and establishes consistency, not correctness. **Граница:** Do not impose a separately owned evaluator on every ordinary rebuild; independence remains necessary when the claimed property or explicit verification claim requires it.
- [Universal design system Rule 12: corpus discovery and conforming resource growth](../../../../../../policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  (§4.3, Rule 12) — Capability is discovered by bounded search over the corpus rather than a hand-maintained central enumeration; a correctly added resource conforming to an existing semantic/protocol class is usable with zero new central code. **Граница:** A genuinely new transport or semantic capability still needs a typed native extension and conformance; search completeness and capacity remain governed and evidenced.
- [Withheld propositions: WP-01/02/03 and activation boundaries](../../../../../../policy-engine/docs/system-design-decisions/withheld-propositions-register.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  — WP-01 retains no posterior mutation pending its live producers and activation; WP-02 supplies no approved routine schedule. **Граница:** This recommendation does not change or activate a withheld proposition. Reconcile later ratification at accepted-source rebind.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="GYD-10"></a>

## GYD-10 — O2 exploratory FDR candidate controller

Исходная запись: [tasks.json](../tasks.json), `tasks[id=GYD-10]`. Review: [root-review](root-review.md#GYD-10).

### Предпочтительное решение

Keep one exploratory controller in the existing DDM/FDR owner and persist its accepted decision into the canonical HypothesisLedger as `candidate_unverified`, with `may_not_use_for` covering authority and direct world write. Reuse `OnlineFDRController`, DDM events, and the ledger, but accept an anomaly as in-budget only under the already accepted FDR plan and a reconciled test denominator, look/window, spend history, and p/e-value validity. The local alpha-wealth result alone is not a proof of FDR control. Keep the O2 false-discovery profile distinct from O1 confirmation; neither an FDR-controlled signal nor an O1 posterior is authority by itself.

### Что переиспользовать

- `policy-engine/src/polisyos/ddm/calibration/multiple_testing.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `OnlineFDRController.test; OnlineFDRDecision`. Implements a small alpha-wealth test decision and records counters/spend; it does not carry the full DDM denominator, dependence proof, or persisted cross-run window.
- `policy-engine/src/polisyos/ddm/contracts/events.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `ShiftDetectedEvent; PerformanceDegradationEvent; ReadinessStateEvent`. Existing DDM signals supply event inputs and window/context fields.
- `policy-engine/src/polisyos/runtime/quality/hypothesis_ledger.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `HypothesisLedgerEntry; persist_hypothesis_ledger; append_hypothesis_ledger_entry`. One append-only ledger already requires candidate authority-slot exclusions and supports candidate_unverified.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Rebind the actual accepted DDM stream/family and FDR plan, then record each eligible hypothesis, complete denominator, look/window, controller state before and after, rule version, source event, and evidence refs.
2. Use the existing controller only for the method and assumptions that the accepted plan actually names. Validate how the real producer constructs its p-values/e-values and how dependence, repeated looks, restarts, and state continuity are handled.
3. Persist a qualifying signal only as a ledger candidate with its spend and explicit `may_not_use_for`; O1 performs separate confirmation and is the only promotion route. A missing guarantee does not block low-authority diagnostics but cannot be labeled an FDR-controlled discovery or promoted.

### Рассмотренные альтернативы

- **Adopt SAFFRON/LORD by name** — Their guarantees depend on assumptions about sequential valid p-values and dependence that the local `OnlineFDRController` and detector outputs do not establish.
- **Use offline Benjamini-Yekutieli as a universal online fix** — Its cited result is an offline procedure under positive regression dependence; it is not a general online controller for arbitrary DDM streams.
- **Replace the stream with e-LOND** — It is a viable research alternative only if native producers can supply valid e-values; an anomaly score cannot be relabeled as one, and a new method requires an explicit accepted decision.

### Free-grow и ресурсы

- **data or config growth:** Add DDM test families/streams and source-specific prior weights only through the accepted FDR plan; append a ledger receipt per look. A correctly added resource in an existing supported semantic/protocol class is discovered through the canonical corpus with zero new central code; new semantics require typed owner extension and conformance.
- **extension boundary:** New test families require p/e-value semantics and dependence/window treatment before entering the denominator; do not silently reset alpha wealth when the stream or process restarts.
- **resource behavior:** Persist sufficient state for exact replay. If denominator, spend state, or source evidence is unavailable, stop candidate admission for that stream while retaining diagnostics as limited evidence.


### Миграция и восстановление

Keep one controller and one candidate ledger. Revoke/quarantine a bad candidate by append-only correction; no O2 event writes the world or creates an alternate ledger. The O2 result remains optional input to O1, never an O3 prerequisite.


### Композиция и owners

- DDM producer -> accepted FDR decision -> persisted receipt -> HypothesisLedger -> O1; include actual run, family, window/look, denominator, spend, rule, source, and `may_not_use_for`.
- P37: validity of each null p/e-value and complete stream/dependence basis must be recomputed or source-reconciled to the qualified producer; its own counter is consumer-asserted for completeness. Use independent verification only when independent correctness is claimed (S0-K14).
- P38: the property is online false-discovery control; the local code tests only `p_value <= alpha_spent`. A p-value chosen after seeing the anomaly, or controller state reset between runs, can be green under this comparison while violating the intended stream guarantee.
- C02: bind the exploratory procedure and its own assumptions to O2; do not present FDR control as confirmatory coverage or use an O1 posterior to imply the O2 procedure was valid.


### Acceptance и различающие проверки

- Positive: one real in-budget DDM anomaly produces an attributed candidate with complete persisted denominator/window/spend, and fresh ledger readback recomputes the decision.
- Negative: missing denominator, invalid or repeated/high q-value, policy-induced observation shift, missing state continuity, and direct world write are refused or remain limited; removal of the FDR/candidate wall makes promotion fail.
- Do not state a new statistical guarantee. If the accepted plan does not match controller behavior or input assumptions, record FDR validity as not_established and leave promotion unavailable.


### Входы и ответственность за их получение

- Real DDM observations and source-qualified detector outputs.
- A complete, accepted hypothesis-family denominator, data-generating/p-value or e-value validity basis, dependence characterization, and stream state across actual looks.


### Когда обоснованно отклониться

- If valid online testing assumptions are not evidenced, maintain `candidate_unverified` only as a no-authority diagnostic with FDR validity `not_established`; do not label it in-budget.
- If the accepted plan uses arbitrary-dependence e-values or another method, require a separately reviewed owner and rule-version decision before changing the controller.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [SAFFRON: an Adaptive Algorithm for Online Control of the False Discovery Rate](https://proceedings.mlr.press/v80/ramdas18a.html) — Online FDR procedures require valid sequential p-values; SAFFRON states conditional super-uniformity assumptions and derives its guarantees from them. **Граница:** It is a method comparison, not the local controller's theorem and not evidence that PolicyOS DDM outputs satisfy its assumptions.
- [The control of the false discovery rate in multiple testing under dependency](https://doi.org/10.1214/aos/1013699998) — Benjamini-Yekutieli prove FDR control for the linear step-up procedure under positive regression dependence on true-null test statistics. **Граница:** That condition is not arbitrary dependence, and the result is an offline multiple-testing result rather than an online DDM-stream guarantee.
- [Online multiple testing with e-values](https://proceedings.mlr.press/v238/xu24a.html) — The paper's e-LOND procedure gives online FDR control under arbitrary, possibly unknown, dependence when its input e-values meet the e-value validity conditions. **Граница:** An anomaly score or current p-value is not an e-value by naming. This is a future alternative only if the accepted DDM plan and native producers supply the required evidence; it is not a default replacement.
- [Adopted target extension: inference plurality](../../../../../../policy-engine/docs/system-design-decisions/policy-design-causal-operating-system-north-star.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  (§10, SDD-C02) — Bayesian confirmatory updates remain supported, while explicitly justified frequentist, sequential, robust, or partial-identification profiles are also permitted for the propositions they support. Posterior probability, coverage, identification sets, and procedural no-number claims must not be silently mixed. **Граница:** C02 appoints no method owner, authorizes no posterior mutation, and does not transfer any method guarantee without its own assumptions and bridge.
- [Universal design system Rule 12: corpus discovery and conforming resource growth](../../../../../../policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  (§4.3, Rule 12) — Capability is discovered by bounded search over the corpus rather than a hand-maintained central enumeration; a correctly added resource conforming to an existing semantic/protocol class is usable with zero new central code. **Граница:** A genuinely new transport or semantic capability still needs a typed native extension and conformance; search completeness and capacity remain governed and evidenced.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="GYD-11"></a>

## GYD-11 — AS3 O3 sealed corpus + consumer mutations

Исходная запись: [tasks.json](../tasks.json), `tasks[id=GYD-11]`. Review: [root-review](root-review.md#GYD-11).

### Предпочтительное решение

Create the distinct AS3 versioned corpus under the appointed runtime/quality packet/oracle owner, preserving the original 24 immutable packets, five isolated O3 consumer mutations, and adjacent valid controls. Its job is to prove the real O3 write path rejects candidate-only and self-confirming evidence, including quarantine after a full reprocessing pass; it is not a second diagnosis holdout or a way to tune O3.


### Что переиспользовать

- `policy-engine/src/polisyos/runtime/quality/world_model_record.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `WorldModelRecord; load_world_model_record`. Typed WMR and exact verified artifact reader are present; no AS3 corpus owner is allocated at C.
- `policy-engine/src/polisyos/fabric/world/events.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `persist_world_event_with_facts`. The existing Fabric event persistence path is the consumer endpoint the mutation corpus should exercise.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.


### Последовательность реализации

1. Freeze the exact original 24 packet identities and five mutation definitions from the accepted GY-AS3 source at rebind; bind each packet to oracle, rule, O1 input, and expected consumer behavior.
2. Run every mutation through the production O3 consumer/writer boundary and use adjacent valid controls. Recompute result from packet bytes and exact refs rather than reading expected marker fields.
3. For the self-confirmation mutation, change the observation process downstream of the policy and then attempt full reprocessing; keep it quarantined and preserve the original failure reason in the receipt.


### Рассмотренные альтернативы

- **Use constructor-only or marker-string mutation tests** — They can pass while the O3 consumer accepts the candidate or reprocessing lifts quarantine; they do not exercise the property.
- **Merge AS2 and AS3 into a single shared corpus** — AS2 admits diagnosis evidence; AS3 probes world-write mutations. Their lock, custodian, and acceptance properties differ.


### Free-grow и ресурсы

- **data or config growth:** Version new packets and mutations append-only; preserve the original 24/5 acceptance set as a stable baseline and add later cases by explicit rule version. A correctly added resource in an existing supported semantic/protocol class is discovered through the canonical corpus with zero new central code; new semantics require typed owner extension and conformance.
- **extension boundary:** New O3 mutation classes need an independent oracle and a real consumer path; no fixture can create authority or substitute for a new causal rule.
- **resource behavior:** Keep the full versioned corpus and reprocessing trace available to audit; if any packet/oracle cannot resolve, the corpus does not certify O3. Do not prune a needed quarantine history.


### Миграция и восстановление

A corpus revision is a new immutable release; quarantine and old receipts remain. O3 stays unavailable when any required mutation witness is missing. No numeric threshold is adopted from these fixtures.


### Композиция и owners

- AS3 oracle -> actual O3 read/branch-write consumer -> persisted failure/success receipt; O3 does not depend on O2.
- P37: corpus membership and mutation expectations are independently_reconciled to the original source; O3 posterior/context refs must be resolve-bind-verify, not caller asserted.
- P38: the property is durable refusal of the five mutations. A corpus validator that checks a seal/expected marker while the branch writer accepts the mutated payload is the divergent case; the writer consumer itself must run.
- The effect-posterior positive requires actual GYD-09/WP activation where that policy applies. Isolated test-policy/corpus research is non-authoritative and cannot mutate that operative posterior or close its activation-dependent positive. Structural admission follows its distinct actual rule in solutions/18-structural-world-learning.md; other engineering preparation continues.


### Acceptance и различающие проверки

- Positive: each of the five named mutations independently fails in the real O3 consumer and adjacent valid controls pass with an admitted posterior.
- Negative: candidate-only evidence, O1/context mismatch, observation-process self-confirmation, replay, and reprocessed quarantine remain red; removing an actual consumer mutation while retaining markers makes the corpus fail.
- Read back the exact sealed corpus version and O3 receipt after execution; do not claim semantic adequacy from packet count alone.


### Входы и ответственность за их получение

- Original GY-AS3 source mutation definitions and independent sealed oracles.
- Real O1 posterior, deployment/observation-process facts, and the actual WMR/Fabric consumer artifacts.


### Когда обоснованно отклониться

- If the five source mutation identities cannot be rebound, retain `not_established` rather than invent substitute cases.
- If a test is excluded as unrelated, finish the prescribed isolation/replay before excluding it; otherwise keep the O3 result unaccepted.

Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.


### Исследование и предел переноса

- [Generalization in Adaptive Data Analysis and Holdout Reuse](https://papers.nips.cc/paper/5993-generalization-in-adaptive-data-analysis-and-holdout-reuse.pdf) — Adaptive reuse of a holdout can overfit to that holdout; their reusable-holdout construction controls this through a restricted validation interface and privacy/stability arguments. **Граница:** This does not make a sealed file or checksum a privacy mechanism. PolicyOS has no adopted query budget or privacy guarantee here, so use this as the reason to protect AS2 and reject post-hoc tuning, not as a transferred guarantee.
- [Universal design system Rule 12: corpus discovery and conforming resource growth](../../../../../../policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  (§4.3, Rule 12) — Capability is discovered by bounded search over the corpus rather than a hand-maintained central enumeration; a correctly added resource conforming to an existing semantic/protocol class is usable with zero new central code. **Граница:** A genuinely new transport or semantic capability still needs a typed native extension and conformance; search completeness and capacity remain governed and evidenced.
- [Withheld propositions: WP-01/02/03 and activation boundaries](../../../../../../policy-engine/docs/system-design-decisions/withheld-propositions-register.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  — WP-01 retains no posterior mutation pending its live producers and activation; WP-02 supplies no approved routine schedule. **Граница:** This recommendation does not change or activate a withheld proposition. Reconcile later ratification at accepted-source rebind.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="GYD-12"></a>

## GYD-12 — O3 versioned world writer: distinct effect and structural inputs

Исходная запись: [tasks.json](../tasks.json), `tasks[id=GYD-12]`. Review: [root-review](root-review.md#GYD-12).

### Предпочтительное решение

Extend the existing runtime/quality WMR owner with two type-specific inputs and one writer. O1 + AS3 + current N12/N13b context and applicable WP policy govern the effect-posterior branch. O2 itself stays candidate-only and may motivate DES-12 research; it never writes or grounds a claim. A returned lineage-bound structural assessment is a distinct CNT-06/native-method input. The actual rule owner supplies the applicable structural write rule; GYD-12 verifies it and may append the qualified structural result without O1 posterior only if that rule permits the exact transition. Missing rule means scoped proposal/conditional work, not implicit permission. Original effect obligations remain required for whole-task GYD-12 completion. Preserve set-valued/competing admissible causal completions rather than forcing a unique graph or effect. The next real policy-design cycle must read the exact new artifact/version. Keep O3 as the only world-growth writer; O2 is not a prerequisite, and UI-08/DS21 is downstream. This update does not itself prove a candidate design’s whole-design joint property: the design consumer may use simulation or a validated exact joint derivation/witness for the concrete property it proves, never marginal/pairwise checks as a substitute. Structural inputs use the separate CNT-06/native-method route in solutions/18-structural-world-learning.md; WP-01/02 are scoped to posterior mutation and cannot prove an edge. The same writer verifies actual applicable structural admission, otherwise preserves candidate/conditional work without operative mutation.


### Что переиспользовать

- `policy-engine/src/polisyos/fabric/world/events.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `persist_world_event_with_facts`. Persists one world event and its emitted facts.
- `policy-engine/src/polisyos/fabric/world/store/snapshots.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `create_world_branch; update_world_branch_head`. Existing branch and snapshot-head owner; one writer/branch-head lease is needed.
- `policy-engine/src/polisyos/runtime/quality/world_model_record.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `WorldModelRecord; persist_world_model_record; load_world_model_record`. Versioned typed WMR persistence/readback with manifest schema and input lineage.
- `policy-engine/src/polisyos/pdc/_impl/world_model_record.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `DeploymentUpdateRefs`. A forward ref carrier only; it declares refs and does not execute deployment/world updates.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.


### Последовательность реализации

1. Resolve and verify the O1 profile-qualified update and AS3 conformance receipt, then compare effect type, jurisdiction/population/resolution, valid time, transaction time, intervention ancestry, observation-process context, and the scope of any competing completions to the current WMR.
2. On one canonical bridge path, create the branch/event from the current snapshot and append the updated WMR with parent/content refs, rule/schema version, attribution, and actor/time provenance. Reject a stale head or mismatched context instead of merging silently.
3. Start a later real cycle from the emitted WMR ref and capture the exact read binding; expose the branch audit and WMR to UI-08/DS21 after producer acceptance.
4. Choose one commit boundary over branch/event/WMR after rebind. If the existing backend transaction covers all of them, commit atomically; otherwise persist an intent with staged immutable objects, fence the branch head and reconcile event/WMR publication idempotently. Incomplete combinations remain unservable/quarantined; a branch CAS alone is not a multi-object transaction.
5. Implement and exercise the distinct structural path in solutions/18-structural-world-learning.md after exact native-owner rebind; do not relabel a set/bound as O1 posterior or grant write authority by scientific qualification.


### Рассмотренные альтернативы

- **Mutate the current WMR or branch in place** — It destroys replayable history and makes rollback/correction indistinguishable from a new claim.
- **Use an external model registry or mutable alias as world head** — A mutable alias can resolve differently later; PolicyOS already has Fabric branch refs and typed WMR lineage.
- **Write exploratory O2 anomalies directly into the world** — It bypasses the confirmatory firewall and turns a candidate into authority.


### Free-grow и ресурсы

- **data or config growth:** Grow one world by appending supported effect/coupling/mechanism/data-requirement changes and admissible alternative completions on versioned WMR branches; conforming resources are corpus-discovered with zero new central code.
- **extension boundary:** New causal variables or edge semantics require a typed owner rule/schema and conformance; context transfer requires explicit transport assumptions/evidence, otherwise retain limited scope. A later whole-design check can use simulation or a validated exact joint witness for the concrete property, never marginal/pairwise substitution.
- **resource behavior:** Retain parent refs, branch events, WMR versions, and required audit lineage under the existing retention owner. A stale head, unsupported effect, or missing CAS capacity fails closed; no unmeasured GC policy is introduced.


### Миграция и восстановление

No in-place update or parallel world store. Correct errors by new event/branch and explicit supersession; retain prior generation. O2-origin effect updates need O1 confirmation; separately qualified structural results follow their actual rule. UI-08 consumes emitted O3 output, not a build prerequisite.


### Композиция и owners

- Profile-qualified O1 update + AS3 pass + current context -> Fabric event/branch -> versioned WMR retaining admitted alternatives -> fresh later-cycle reader -> DS21 projection/audit; keep whole-design joint validation as a separately consumed property.
- P37: O1 artifact identity, AS3 result, WMR inputs, and branch-head currency are resolve-bind-verify or independently_reconciled; a caller-provided branch id is consumer_asserted.
- P38: the property is that the later cycle reads the exact admitted updated world; checking only `posterior_update_refs` or a branch-name field diverges when the referenced artifact is missing, mismatched, stale, or not bound into the loaded WMR.
- Transportability requires explicit source/target graph assumptions; no posterior alone licenses a move across population, jurisdiction, period, or interference context.
- C01: for any later whole-design claim, accept simulation or a validated exact joint derivation/witness only for the property/assumptions it actually proves; neither marginal nor pairwise checks can stand in for joint analysis, and model truth still needs grounding.
- The effect-posterior positive requires actual GYD-09/WP activation where that policy applies. Isolated test-policy/corpus research is non-authoritative and cannot mutate that operative posterior or close its activation-dependent positive. Structural admission follows its distinct actual rule in solutions/18-structural-world-learning.md; other engineering preparation continues.
- CNT-06/native method assessment -> GYD-12 type-specific admission -> append-only WMR/Fabric -> fresh later reader; question-scoped join, not a whole-task start edge.
- O1 + AS3 + current N12/N13b context and applicable WP policy govern the effect-posterior branch. O2 itself stays candidate-only and may motivate DES-12 research; it never writes or grounds a claim. A returned lineage-bound structural assessment is a distinct CNT-06/native-method input. The actual rule owner supplies the applicable structural write rule; GYD-12 verifies it and may append the qualified structural result without O1 posterior only if that rule permits the exact transition. Missing rule means scoped proposal/conditional work, not implicit permission. Original effect obligations remain required for whole-task GYD-12 completion.


### Acceptance и различающие проверки

- Positive: O1 + AS3 + exact current context produce an append-only branch/event and WMR preserving any supported competing completions; the next real cycle reads it by exact content/version ref. A downstream joint-design claim is accepted only with simulation or a validated witness for that joint property.
- Effect-branch negative: raw candidate, stale context, self-confirmation or replay cannot advance the head; removing applicable O1/AS3 admission refuses that effect write. Structural-branch negative/removal separately checks actual scientific warrant and write rule; lack of posterior alone does not reject a supported structural input.
- The DS21/UI-08 readout is a downstream consumer and acceptance dependency, never an O3 build prerequisite or authority by adjacency.
- Crash before/after each event, branch-head and WMR write and retry the same intent. A fresh next-cycle reader sees either one complete admitted generation or explicit pending/refused state, never a half-published world or duplicate growth.
- Exercise structural positive, changed-evidence adversarial and remove-warrant controls in solutions/18-structural-world-learning.md; no operative positive is claimed absent an actual write-admission rule.


### Входы и ответственность за их получение

- O1 profile-qualified update and AS3 consumer-mutation receipt, with any independent-correctness claim supported by a genuinely independent check as scoped by K14.
- Real current N12/N13b source/context evidence, actual branch-head state, and the later cycle's source/version readback.
- Exact structural assessment/profile, native qualifier/verifier and applicable O3 structural write policy. Missing internal bridge is engineering; a genuinely absent accepted rule is a scoped proposal, not permission.


### Когда обоснованно отклониться

- If the target context differs and transport evidence/selection assumptions are absent, append no general effect; retain the narrower scope or a typed limitation.
- If exact branch-head compare-and-update or currentness cannot be proven at rebind, keep the writer refused; do not create a parallel coordinator.

Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.


### Исследование и предел переноса

- [Transportability of Causal and Statistical Relations: A Formal Approach](https://ojs.aaai.org/index.php/AAAI/article/view/7861) — Selection diagrams make differences and commonalities between source and target environments explicit and support deciding whether a causal effect is identifiable in the target from available source experiments and target observations. **Граница:** This does not license automatic generalization to a new population, time, or interference regime. It depends on a causal graph and evidence for its selection assumptions.
- [The Update Framework Specification, version 1.0.36](https://theupdateframework.github.io/specification/v1.0.36/) — TUF specifies version, signature, hash, and expiry checks that detect rollback, freeze, and mix-and-match attacks in software update metadata. **Граница:** TUF is not a causal model-update protocol. Transfer only the narrow design lesson that a consumer resolves a pinned version and rejects stale or mismatched lineage; do not import its signing roles or claim its security properties for Fabric.
- [MLflow Model Registry Workflows](https://mlflow.org/docs/latest/ml/model-registry/workflow/) — MLflow distinguishes exact model-version references from mutable aliases; alias reassignment can change which version a later consumer resolves. **Граница:** This is an implementation example, not a recommendation to add MLflow or use aliases for PolicyOS authority. Audit and causal lineage should resolve immutable artifact refs.
- [Adopted reading clarification: competing causal completions and claim-type-specific grounds](../../../../../../policy-engine/docs/system-design-decisions/policy-design-causal-operating-system-north-star.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  (§10, SDD-B01) — A singular world-model reference may be credal/set-valued and admit competing causal completions. Grounding is claim-type-specific: causal claims need causal grounds, measurement claims need construct/method grounds, and value claims need a declared frame and applicable mandate. **Граница:** This adopted target clarification does not certify implementation or impose a unique causal structure; actual admission still needs the relevant owner, evidence, and scope.
- [Adopted target extension: joint evaluation witness](../../../../../../policy-engine/docs/system-design-decisions/policy-design-causal-operating-system-north-star.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  (§10, SDD-C01) — Whole-design joint evaluation may use simulation or an exact joint derivation/other validated joint witness for the concrete property it actually proves; marginal or pairwise checks do not substitute. Model truth and grounding remain separate. **Граница:** The alternative needs an explicit property, assumptions, consumer, and falsifier; this target wording does not certify a runtime implementation.
- [Adopted target extension: inference plurality](../../../../../../policy-engine/docs/system-design-decisions/policy-design-causal-operating-system-north-star.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  (§10, SDD-C02) — Bayesian confirmatory updates remain supported, while explicitly justified frequentist, sequential, robust, or partial-identification profiles are also permitted for the propositions they support. Posterior probability, coverage, identification sets, and procedural no-number claims must not be silently mixed. **Граница:** C02 appoints no method owner, authorizes no posterior mutation, and does not transfer any method guarantee without its own assumptions and bridge.
- [Stage 0 custody kernel K14 scope amendment](../../../../../../policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  (§4.2, S0-K14) — Independence is required for verification claims, including benchmark-oracle claims and assertions of independent validation. A same-code rebuild is permitted and establishes consistency, not correctness. **Граница:** Do not impose a separately owned evaluator on every ordinary rebuild; independence remains necessary when the claimed property or explicit verification claim requires it.
- [Universal design system Rule 12: corpus discovery and conforming resource growth](../../../../../../policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  (§4.3, Rule 12) — Capability is discovered by bounded search over the corpus rather than a hand-maintained central enumeration; a correctly added resource conforming to an existing semantic/protocol class is usable with zero new central code. **Граница:** A genuinely new transport or semantic capability still needs a typed native extension and conformance; search completeness and capacity remain governed and evidenced.
- [Withheld propositions: WP-01/02/03 and activation boundaries](../../../../../../policy-engine/docs/system-design-decisions/withheld-propositions-register.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  — WP-01 retains no posterior mutation pending its live producers and activation; WP-02 supplies no approved routine schedule. **Граница:** This recommendation does not change or activate a withheld proposition. Reconcile later ratification at accepted-source rebind.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="GYD-13"></a>

## GYD-13 — CB2 operator-trial production consumer

Исходная запись: [tasks.json](../tasks.json), `tasks[id=GYD-13]`. Review: [root-review](root-review.md#GYD-13).

### Предпочтительное решение

Wire a discoverable production caller through the existing `runtime/quality/operator_comprehension.py` owner and diagnostic event log. Extend its current synthetic-only run path to consume a real operator trial event and write/read back the exact persisted receipt; do not create another trial engine. Preserve the instrument's non-authority: a demonstrated instrument is not a claim that a human understood the policy, and the GY-CB1 residual/WP-09 remains withheld.

### Что переиспользовать

- `policy-engine/src/polisyos/runtime/quality/operator_comprehension.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `run_instrument; read_instrument_result; recompute_instrument_payload`. The owner seals a corpus, scores trials, emits a sensitive DiagnosticEvent, persists payload through RuntimeDiagnosticEventLog, and recomputes on read; current run explicitly uses a synthetic tenant/profile.
- `policy-engine/src/polisyos/runtime/quality/README.md@dccea950845cda5b38f026e7770c07819d31f4d9` — `operator_comprehension owner notes`. Documented owner keeps `human_comprehension_established` false; CB2 is the separate production consumer obligation.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. At accepted-source rebind, name the real operator-trial producer, event identity, source/tenant/role/time fields, command registration path, and diagnostic event store reader.
2. Extend the canonical instrument entry point to accept only source-resolved real trial events for production execution; preserve sealed corpus scoring and sensitive payload policy, and emit a typed receipt with actual invocation/input refs.
3. Make the discoverable command read the just-written event back and recompute the score; keep sample credit and human-comprehension projections separate from instrument conformance.

### Рассмотренные альтернативы

- **Credit synthetic fixtures or a marker-only command registry entry** — It does not prove a real command invoked the producer or that an actual operator trial was persisted.
- **Build a generic trial scheduler/engine** — The existing instrument and diagnostic event owner already own scoring and persistence; the missing work is the real production caller/bridge.

### Free-grow и ресурсы

- **data or config growth:** Add trials under versioned sealed corpus/design configs and retain one diagnostic receipt per real invocation. A correctly added resource in an existing supported semantic/protocol class is discovered through the canonical corpus with zero new central code; new semantics require typed owner extension and conformance.
- **extension boundary:** New trial semantics stay in the operator-comprehension owner; external operator identity/session facts must arrive as typed evidence, not caller-selected names or LLM labels.
- **resource behavior:** Use the current sensitive-payload custody and dedupe semantics; if the real event cannot be resolved, or persistence/readback is unavailable, award no sample credit and do not substitute synthetic data.


### Миграция и восстановление

Keep the synthetic path explicitly research-only. Until the real caller and readback land, CB2 remains incomplete and WP-09/human comprehension remains false. Failed or withdrawn trials are retained as diagnostics rather than credited silently.


### Композиция и owners

- Real operator event -> production command -> canonical instrument producer -> persisted diagnostic event/receipt -> fresh recomputing reader -> audit/command surface.
- Rule 12: a conforming new corpus/config resource is discovered through the owner’s existing corpus with zero new central code; a new trial semantic or external operator fact still requires its typed native owner/evidence.
- P38: the property is a real operator trial passing through the production command; `run_instrument` currently emits a synthetic-tenant research event. A synthetic payload with a production-looking marker is the divergent case.


### Acceptance и различающие проверки

- Positive: a real operator invocation constructs the trial, persists one receipt, and the command's fresh readback recomputes it from stored raw event/corpus/design refs.
- Negative: missing call, missing event, synthetic tenant, altered payload, or no source/content bind fails even when command markers remain; removing the production call makes the same consumer fail.
- No sample or surface may say human comprehension is established; GY-CB1's semantic paraphrase and institutional adjudication residuals remain visible.


### Входы и ответственность за их получение

- A real operator-session/trial event emitted by the permitted source with its identity, context, and time provenance.
- The sealed CB1 instrument/corpus and the canonical diagnostic event-store receipt.


### Когда обоснованно отклониться

- If the real trial event producer is not appointed or the diagnostic-event store cannot resolve provenance, keep the capability `absent/unallocated` or `consumer_missing` as established by rebind and award no credit.
- If a requested result is human comprehension or legal/institutional adjudication, route it to the proper external authority rather than changing the instrument status.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [Universal design system Rule 12: corpus discovery and conforming resource growth](../../../../../../policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  (§4.3, Rule 12) — Capability is discovered by bounded search over the corpus rather than a hand-maintained central enumeration; a correctly added resource conforming to an existing semantic/protocol class is usable with zero new central code. **Граница:** A genuinely new transport or semantic capability still needs a typed native extension and conformance; search completeness and capacity remain governed and evidenced.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="GYD-14"></a>

## GYD-14 — ML2 Lex rendition production consumer

Исходная запись: [tasks.json](../tasks.json), `tasks[id=GYD-14]`. Review: [root-review](root-review.md#GYD-14).

### Предпочтительное решение

Extend the existing Lex `knowledge/multilingual_assurance.py` producer/reader through one appointed production rendition consumer, using real rendition bytes and an independently reconciled full source denominator. Version any change to its synthetic-candidate contract. The receipt remains a finite, non-authoritative candidate comparison: missing trust roots mean authority admission refuses, and signer/holder/trust-root slots remain empty while WP-11/WP-12 and legal equivalence stay withheld.

### Что переиспользовать

- `policy-engine/src/polisyos/lex/knowledge/multilingual_assurance.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `AssurancePacket; run_assurance; replay_assurance_result; read_assurance_result`. Existing CAS-backed candidate assurance stores exact packet/result and replays content; packet requires `ground_truth=synthetic_candidate`, empty qualified holders, and explicit non-authority limits.
- `policy-engine/src/polisyos/lex/knowledge/README.md@dccea950845cda5b38f026e7770c07819d31f4d9` — `Candidate multilingual assurance`. Candidate MAEP instrument is owned here; no exact production consumer is identified at C.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Appoint the real Lex rendition consumer and exact source inventory that defines all required rendition/context members; preserve canonical CAS as byte custody.
2. Feed the real source and target rendition bytes through the canonical assurance owner and persist a receipt bound to every member, denominator, language/jurisdiction, rule, source version, and validity time.
3. Reconcile the consumer's denominator against the authoritative source inventory, then replay and read the exact receipt. Keep candidate semantic frames marked consumer_asserted and keep legal authority/equivalence blocked when trust-root evidence is absent.

### Рассмотренные альтернативы

- **Create a second Lex assurance engine or ledger** — The existing module owns candidate comparison, CAS persistence, revocation, and readback; the open obligation is its real production consumer.
- **Treat the current synthetic frame or matching status/action profiles as legal equivalence** — Those frames are consumer-asserted; natural-language correspondence and institutional adjudication are not established, and the holder/trust roots are deliberately empty.

### Free-grow и ресурсы

- **data or config growth:** Add real rendition sets and source contexts as versioned inputs; preserve complete denominator and exact text digests per receipt. A correctly added resource in an existing supported semantic/protocol class is discovered through the canonical corpus with zero new central code; new semantics require typed owner extension and conformance.
- **extension boundary:** Real text comparison may remain diagnostic. Legal meaning, source authority, equivalence, glossary release, RTL accessibility, and qualified holder semantics require their own typed evidence/authority and cannot be inferred from candidate matching.
- **resource behavior:** Bound readback to the source-declared complete denominator and existing CAS custody; missing/partial members or missing trust roots refuse the relevant admission. Never count a self-declared subset as the full denominator.


### Миграция и восстановление

Keep existing v1 candidate artifacts replayable; any real-rendition input contract is a new schema/rule version and does not promote old synthetic receipts. Revoke by existing append-only candidate invalidation. Keep signers, holders, and roots empty until externally appointed evidence is verified.


### Композиция и owners

- Real rendition producer -> canonical Lex comparator/CAS -> exact receipt readback -> appointed consumer/audit surface.
- Rule 12: a conforming rendition resource in an existing semantic class is discovered with zero new central code; a new legal/equivalence semantic still requires a typed native extension and appointed authority evidence.
- P38: the property is every required real rendition/context being covered. Current code checks equality against the packet's own `contexts`; if that declaration omits a real source context, the check remains green. Reconcile the declaration to the independent source inventory.


### Acceptance и различающие проверки

- Positive: real rendition source set resolves to one complete, content-bound receipt whose full denominator is read back from the appointed source inventory.
- Negative: partial/forged denominator, wrong source content, stale rule/validity, unresolved CAS item, or absent required trust root refuses; source/content removal makes denominator readback fail.
- Projection preserves candidate-only authority, `may_not_use_for` and withheld propositions; no legal equivalence or RTL authority claim is emitted.


### Входы и ответственность за их получение

- Real source/target rendition bytes and the independently owned inventory of required locales, contexts, and versions.
- Any authority-grade trust-root, holder, glossary, legal, or accessibility evidence, only when actually appointed and independently verified.


### Когда обоснованно отклониться

- If source membership or full denominator cannot be independently reconciled, produce no assurance credit beyond the bounded candidate diagnostic.
- If a trust root is absent, do not fill it with a local test signer or synthetic frame; retain the typed-empty authority state.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [Universal design system Rule 12: corpus discovery and conforming resource growth](../../../../../../policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  (§4.3, Rule 12) — Capability is discovered by bounded search over the corpus rather than a hand-maintained central enumeration; a correctly added resource conforming to an existing semantic/protocol class is usable with zero new central code. **Граница:** A genuinely new transport or semantic capability still needs a typed native extension and conformance; search completeness and capacity remain governed and evidenced.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="GYD-15"></a>

## GYD-15 — FA1 four owner-allocated authority capabilities

Исходная запись: [tasks.json](../tasks.json), `tasks[id=GYD-15]`. Review: [root-review](root-review.md#GYD-15).

### Предпочтительное решение

Treat FA1 as four separately source-qualified capabilities under the existing Foundry catalog/discovery boundary, with Runtime as consumer; preserve the current negative-only production authority graph until each required chain is independently admitted as GYD-15 requires. Reuse `dependency_authority.py`, Core CAS, existing evidence contracts, and the snapshot-to-N8 transport. Do not flip registry rows, add a generic authority engine, or let observations/local signers promote. FR-AUTH-01 is a proposed research/scheduling input, not ratified policy or proof. Under Rule 12, a correctly added resource conforming to an existing class must be discoverable with zero new central code; only a genuinely new semantic/transport needs typed native extension and conformance.

### Что переиспользовать

- `policy-engine/src/polisyos/foundry/methods/catalog/dependency_authority.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `_NoRuntimeSubtreeCutoffAuthority.preflight; _ProductionMethodCatalogDependencyAuthority.resolve; build_production_method_catalog_dependency_authority`. Existing default production path resolves canonical source then returns runtime-cutoff refusal; public result ABI is currently negative-only.
- `policy-engine/src/polisyos/foundry/methods/catalog/snapshot.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `build_method_catalog_snapshot; persist_method_catalog_snapshot`. Existing catalog snapshot builders/persisted artifact are the production route to preserve and extend after owner review.
- `policy-engine/docs/superpowers/specs/2026-09-10-producers-foundry-authority.md@dccea950845cda5b38f026e7770c07819d31f4d9` — `FR-AUTH-01 proposed four-capability design`. Proposal document observed at historical implementation pin; not a ratified authority mechanism.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. For `owner_enforced_runtime_subtree_cutoff`, define the protected interval and exact executable/root/descendant-byte set, then appoint the enforcement owner and independent reader required by this FA1 capability. Keep the current preflight refusal until its independent cutoff-basis receipt is consumed.
2. For `owner_resolved_resolution_receipt_store`, extend Core CAS and Foundry evidence contracts with a real authoritative writer/resolver, content/scope binding, lineage/time/revocation and exact reader; reject present-but-forged, stale, cross-environment, and replacement receipts.
3. For `platform_toolchain_admission`, bind the admitted interpreter/platform/package evidence to the exact executable, root, installation, and cutoff receipt while keeping source identity, runtime-instance identity, and package coordinates distinct.
4. For `production_data_trust_policy`, resolve purpose/role/root/content and tenant/time/revocation through existing authority interfaces; absent institutional evidence remains typed-empty. Route each receipt through the current production builder and N8 consumer before admitting any positive result.
5. Implement missing native producers/bridges/readers or enforcement inside the assigned scope after owner allocation; do not stop by classifying internal engineering as an external input. Real institutional appointments, authentic observations and permission facts remain separately sourced and cannot be fabricated.

### Рассмотренные альтернативы

- **Populate the authority registry or add more candidate runtime walks** — Rows/manifests/diagnostics do not prove the independent cutoff-basis claim or producer authority; the current production preflight is deliberately refusal-only.
- **Use a local signer, new parallel authority service, or repeated self-walk as the trust root** — It fails FA1’s explicit independent-source/read requirement, duplicates the canonical owner, and can mint authority from the same writer being checked.

### Free-grow и ресурсы

- **data or config growth:** Admit additional scope-bound receipts and tool/data rules only inside the four named capability classes and their existing registries/contracts. A correctly added resource in an existing supported semantic/protocol class is discovered through the canonical corpus with zero new central code; new semantics require typed owner extension and conformance.
- **extension boundary:** A conforming receipt/rule inside an existing semantic class is corpus-discovered with zero central enumeration/code. A genuinely new transport or authority semantic needs a typed native extension and conformance; no arbitrary plugin/rule becomes authority by configuration alone.
- **resource behavior:** Each owner sets a declared scope/retention/capacity policy with versioned receipts. Exceeding or losing capacity refuses admission; never fall back to candidate observation or silently drop source members.


### Миграция и восстановление

Keep all four capabilities `absent/unallocated` until appointed owners emit receipts and the current consumer verifies them. Partial engineering can improve diagnostics but cannot turn the positive ABI on. Roll back to the existing negative-only refusal; no authority is inferred from FR-AUTH-01 prose or institutional appointment adjacency.


### Композиция и owners

- Per capability: typed contract -> named non-test producer -> persisted receipt -> exact reader/resolver -> production method-catalog/N8 consumer -> audit projection, with rule/schema/time/provenance/scope.
- P37: the mandatory FA1 cutoff basis is `independently_reconciled` to the actual protected source set; exact receipt authenticity/resolution is recomputed by its reader. Apply independence to the explicit FA1 independent-correctness claim and any property that requires it, not to every ordinary rebuild (K14). Toolchain/source identity may be institutionally supplied but cannot alone turn the gate green; absent trust inputs remain not_established.
- P38 mandatory falsifier: the property is writer-independent custody of the actual admitted subtree; equal candidate walks or a signed declared path list test only the declaration. Change the actual subtree while retaining that declaration/signature and require refusal.
- Also probe stale/replaced/cross-environment receipts, copied or redirected runtime, swapped install, and source-data revocation at the exact production consumer.


### Acceptance и различающие проверки

- Positive only after each capability has an appointed native owner, required producer/persisted-receipt chain, and the independent reader/verification that FA1 explicitly requires; read back exact bytes and source/version.
- Negative for missing, unverifiable, self-authored, wrong-scope, stale, revoked, cross-environment, or replacement receipts; removing any producer/admission binding makes the unchanged negative fail.
- Mandatory cutoff test mutates the actual subtree while preserving the declared cutoff/path list and signature; independent reconciliation must turn the gate red. Keep candidate observations non-authoritative throughout.


### Входы и ответственность за их получение

- An independently enforced runtime-subtree cutoff primitive and protected-set evidence required by FA1’s explicit independent-source claim.
- Owner-resolved receipt source, actual platform/toolchain identity, and qualified production-data trust/root/role/tenant evidence from their source owners.


### Когда обоснованно отклониться

- If an owner is not appointed or the independent source required by FA1 cannot be resolved, leave the capability absent/unallocated and retain production refusal. This requirement is property-specific and does not impose an unrelated independent evaluator for consistency-only rebuilds.
- If FR-AUTH-01 is not ratified or GY-DEF22 adjudication remains unappointed, record the decision boundary; do not claim authority or block separate bounded engineering solely by adjacency.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [The Update Framework Specification, version 1.0.36](https://theupdateframework.github.io/specification/v1.0.36/) — TUF specifies version, signature, hash, and expiry checks that detect rollback, freeze, and mix-and-match attacks in software update metadata. **Граница:** TUF is not a causal model-update protocol. Transfer only the narrow design lesson that a consumer resolves a pinned version and rejects stale or mismatched lineage; do not import its signing roles or claim its security properties for Fabric.
- [Universal design system Rule 12: corpus discovery and conforming resource growth](../../../../../../policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  (§4.3, Rule 12) — Capability is discovered by bounded search over the corpus rather than a hand-maintained central enumeration; a correctly added resource conforming to an existing semantic/protocol class is usable with zero new central code. **Граница:** A genuinely new transport or semantic capability still needs a typed native extension and conformance; search completeness and capacity remain governed and evidenced.
- [Stage 0 custody kernel K14 scope amendment](../../../../../../policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  (§4.2, S0-K14) — Independence is required for verification claims, including benchmark-oracle claims and assertions of independent validation. A same-code rebuild is permitted and establishes consistency, not correctness. **Граница:** Do not impose a separately owned evaluator on every ordinary rebuild; independence remains necessary when the claimed property or explicit verification claim requires it.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.
