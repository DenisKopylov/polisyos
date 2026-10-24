# Содержательный дизайн и обучение: предпочтительные решения R14

Baseline плана `c8986d035f12c1c3d9e5d0d57e369fe8257bccbc`; статические code anchors `dccea950845cda5b38f026e7770c07819d31f4d9` — не принятый E02 и не runtime proof. Все работы — после actual E02 acceptance и affected-scope rebind. [Архитектура](../architecture/04-generative-search-learning-and-documents.md), [аудит](../assurance/07-r14-capability-audit.md), [качество](../assurance/08-productive-search-and-document-quality.md).

Карточки сохраняют существующие owners и native status semantics. Новые имена здесь — planning task IDs, не product enums. Отклонение возможно при source-bound обосновании; изменение SDD требует отдельного согласования.

<a id="DES-01"></a>
## DES-01 — Preserve intent and competing problem framings through actual design intake

Extend the existing request-frame/formulator handoff, preserving the original question and distinct proposed framings, affected populations, goals, value assumptions, mechanism hypotheses and declared unknowns. G6 remains bounded intake and tool routing; N4 owns intervention generation. A suggested frame or user preference is not a political mandate. Carry original language and semantic-loss records into the persisted hypothesis/candidate owner.

**Переиспользовать:** `policy-engine/src/polisyos/runtime/quality/proving_ground/bounded_request_agent.py@dccea950845cda5b38f026e7770c07819d31f4d9`; `policy-engine/src/polisyos/scientist/policy_design/formulator.py@dccea950845cda5b38f026e7770c07819d31f4d9`; `policy-engine/src/polisyos/scientist/nodes/builtins/planning/draft_policy_options.py@dccea950845cda5b38f026e7770c07819d31f4d9`.

**Шаги:**

1. Trace the actual request producer, formulator sink and N4 consumer on accepted E02. Reuse their request/hypothesis contracts; appoint one native writer for missing binding.
2. Preserve original user intent and proposed alternatives separately, with parent refs, selected scope, stated assumptions and unbound concepts. Ask for real clarification only where a selected consequential interpretation cannot be safely expressed as alternatives.
3. Bind the chosen frame to the actual generation request and retain unchosen frames. Unsupported grammar content remains a durable hypothesis/refinement request, not a silently simplified executable candidate.
4. Join existing UI-05 private intake to a fresh candidate/ledger reader. Prove that a meaning-changing scope edit produces a new branch and changes the generation input.

**Композиция и границы:**

- UI-05 owns Clerk/API wiring; DES-01 owns native intent bridge only. Shared formulator edits with DES-02/08 need one writer.
- Actual N4 output is required for composed acceptance; interface agreement permits early independent intake preparation.

**Acceptance / adversarial / removal:**

- An ambiguous but usable question yields distinct explicit framings; an authorized selected frame reaches N4 with exact original intent and unknowns. A known-solvable bounded case yields real candidate generation, not only clarification/refusal.
- A prompt that substitutes a different population, goal, jurisdiction or value basis cannot silently become the chosen task. Prompt injection cannot expand tools or egress rights; unrepresentable ideas survive as unbound hypotheses.
- Remove the original-intent/selection bridge while keeping frame IDs: fresh generation-input and reviewer comparisons detect the meaning loss.

**Входы и ограничения:**

- Existing request/frame/mandate records and exact user selection where needed; absent political mandate limits authority, not hypothetical framing.

**Не выбранные альтернативы:**

- Create a second conversational policy engine: duplicates G6/N4.
- Require complete evidence before proposing a frame: prevents useful research.
- Silently fill unspecified goals: invents policy authority.

**Поверхность:** UI-05 reviewer/expert intake and hypothesis/frontier refs; no G6 PUBLIC recommendation text.

**Free-grow / ресурсы:** New questions, languages and conforming facets flow through the same grammar/registries; new semantic classes need a versioned adapter, not a closed task-template menu.

**Миграция:** Version native artifacts and consumers where needed; legacy provenance/claims are not backfilled as verified. Read old outputs with explicit limits; re-evaluate only actual affected current uses.

**Rollback:** Suspend affected new use; preserve immutable history and legally permitted receipts; revert behavior by a forward repair/version, not history rewrite. Never restore revoked authority or rights.

**Параллельность:** P0-ACCEPT plus interface agreements: UI-05. Actual producer outputs are mandatory for composed acceptance; interfaces do not simulate final evidence. Exact shared paths and semantic owners stay single-writer.

**Canonical writer allocation:** DES-01 is the single formulator.py writer for this cut and composes DES-02/08/09 requests. DES-02 is the single hypothesis_ledger.py writer. DES-09 owns prompt_tool_ledger.py/context invocation receipt and supplies its ref; other tasks consume these interfaces. Independent preparation remains allowed on disjoint files.

<a id="DES-02"></a>
## DES-02 — Generate genuinely different policy mechanisms and hypotheses through native N4

Wire/extend the existing N4 drafter/formalizer/critic and grammar fallback into a persisted alternative set. LLMs propose causal hypotheses, operators, target slots, direct effects, intended effects and combinations; native compilation reports exact representability and loss. Grounded executable proposals and unbound research hypotheses remain distinct. Do not manufacture diversity with names or random parameter changes.

**Переиспользовать:** `policy-engine/src/polisyos/runtime/quality/design_generation.py@dccea950845cda5b38f026e7770c07819d31f4d9`; `policy-engine/src/polisyos/scientist/policy_design/formulator.py@dccea950845cda5b38f026e7770c07819d31f4d9`; `policy-engine/src/polisyos/runtime/quality/hypothesis_ledger.py@dccea950845cda5b38f026e7770c07819d31f4d9`.

**Шаги:**

1. Rebind N4 proposal channels, InterventionAtomBinding and hypothesis sink; preserve historical N4 requirements and existing candidate firewall.
2. Use actual traced model outputs for the LLM channel; retain deterministic/grammar channels with truthful attribution and independent availability. Persist candidate ancestry, generation inputs, rejections, incompleteness and declared unknowns.
3. Compare actual emitted candidates by intervention/effect structure and context. Structural keys and embeddings assist deduplication but are not an oracle of semantic equivalence. Preserve new/unclassified mechanisms for review.
4. Route executable, source-bound proposals to the existing N5 evaluator and others to the existing Research/refinement/acquisition route. Demonstrate at least three real alternatives on the selected historically required N4 diversity case; do not fabricate three on cases whose constraints permit fewer.

**Композиция и границы:**

- DES-02 owns N4 generation; DES-03 owns native numerical trials; DES-04 owns N6 feedback/fronts.
- N4 historical executed status is preserved; this task closes the explicit substantive-quality and persistence/composition residual, not a wholesale rewrite.

**Acceptance / adversarial / removal:**

- On a known-groundable case the real N4 route produces the required alternative set, including an independently checked material mechanism distinction, persists it and a fresh N6 consumer reads it. A newly registered conforming operator is discovered without a search-code edit.
- Synonyms/IDs do not inflate diversity; similarly worded but causally different proposals do not collapse. Missing world/evidence/law facts remain declared unknown and cannot execute a fake bound effect. A missing provider leaves an honest degraded mode and usable grammar candidates.
- Replace the set with paraphrases while retaining count/diversity markers; the semantic check fails. Remove candidate-firewall/source binding; protected downstream consumers refuse.

**Входы и ограничения:**

- Selected model access/allowed context for live LLM proof; grammar/resources and controlled multi-mechanism case. Model absence does not erase non-LLM candidates; live-LLM outcome remains UNRUN.

**Не выбранные альтернативы:**

- Generate all candidates from fixed domain templates: loses free growth.
- Treat model novelty claims as verified diversity: proxy gate.
- Replace native N4 with a new generic agent loop: duplicate owner.

**Поверхность:** Private/reviewer alternatives, unresolved hypothesis and compilation-loss view; per-channel source lineage and actual emitted coverage.

**Free-grow / ресурсы:** New registered mechanisms/facets are discovered by the existing grammar; unrepresentable content remains research input. Bound candidate counts/context and persist references rather than duplicate source payloads.

**Миграция:** Version native artifacts and consumers where needed; legacy provenance/claims are not backfilled as verified. Read old outputs with explicit limits; re-evaluate only actual affected current uses.

**Rollback:** Suspend affected new use; preserve immutable history and legally permitted receipts; revert behavior by a forward repair/version, not history rewrite. Never restore revoked authority or rights.

**Параллельность:** P0-ACCEPT plus interface agreements: DES-01, DES-09. Actual producer outputs are mandatory for composed acceptance; interfaces do not simulate final evidence. Exact shared paths and semantic owners stay single-writer.

**Root review refinement:** On the designated productive positive control, the alternative must answer a predeclared substantive decision need or identify a specific evidence path that resolves it. Structural validity/diversity alone does not establish productive capability. Independent labels and the frozen DES-10 criterion decide that bounded claim.

**Canonical writer allocation:** DES-02 owns N4 and hypothesis_ledger.py; formulator.py edits are handed to DES-01 as the single writer. DES-09 supplies invocation refs. N4 fresh consumer must resolve the persisted invocation ref, not a declared model label.

<a id="DES-03"></a>
## DES-03 — Compose structural proposals with typed numerical and multiobjective search

Extend the canonical Scientist hierarchical coordinator: structural proposals define typed discrete/conditional spaces, native search methods evaluate numerical parameters and constraints, and existing joint simulation supplies candidate evaluation. Reuse BO/grid/random/multiobjective implementations by method suitability. Preserve a nondominated set and unknown/incomparable outcomes; no hidden social scalarization or second optimizer.

**Переиспользовать:** `policy-engine/src/polisyos/scientist/policy_design/search.py@dccea950845cda5b38f026e7770c07819d31f4d9`; `policy-engine/src/polisyos/scientist/methods/search/strategies/space.py@dccea950845cda5b38f026e7770c07819d31f4d9`; `policy-engine/src/polisyos/scientist/methods/search/strategies/multi_objective.py@dccea950845cda5b38f026e7770c07819d31f4d9`; `policy-engine/src/polisyos/scientist/nodes/builtins/planning/run_hierarchical_policy_search.py@dccea950845cda5b38f026e7770c07819d31f4d9`.

**Шаги:**

1. Trace accepted coordinator, Stage B evaluator, SearchSpace and native workflow; appoint one search.py writer shared with DES-08. Truthfully repair hybrid_seed_llm_assisted if the static no-invocation divergence survives rebind.
2. Bind each actual trial to structure, method/executable identity, bounds/units, objective directions, constraints, source/model/rule/context and resource usage. Reject invalid conditional/category combinations before execution.
3. Feed real jointly simulated results from GYD-30 and value sets from GYD-31 into search. Hard authority constraints cannot be traded for a penalty; exploratory penalties never certify feasibility.
4. Evaluate across the selected admissible model/scenario set. Separate optimizer/simulation uncertainty from causal-world uncertainty; retain model-sensitive alternatives without invented probabilities or weights.
5. Use exact small oracles, baseline and equal-budget comparisons to select a strategy; preserve no-intervention comparator, sensitivity, truncation and unsupported-method limitations.

**Композиция и границы:**

- Recover a stochastic invocation through its existing native intent/trial/attempt owner: bind the selected realization or method-qualified realization set to that intent and its accepted result. Late, duplicate or changed replies under the same intent remain attempt outputs, not additional independent evidence; preserve their actual outcomes/cost and dependence. A safe pure retry may reconstruct a qualified frozen stream/state or use a method-qualified replacement realization with an explicit successor basis and full failure/selection denominator. Do not silently replace an already referenced realization, use retry-until-favourable selection, or force every pure local retry into external-effect reconciliation. Only an explicit new replicate changes the replicate basis; independence still needs the method criterion. No universal one-draw-per-job restriction, RNG schema, new intent ledger or global result lock; see R16 C3/C5 R24 companion.

- GYD-30 alone owns joint CompositionCertificate; GYD-31 owns ValueOuterSet. DES-03 consumes actual outputs, not new certificates.
- GYD-23 Slice0 remains BIND/ESTIMATE/VERIFY; this richer search is a separately selected existing Scientist/N4-N6 route.

**Acceptance / adversarial / removal:**

- For the selected stochastic method, interrupt between evaluation and result persistence, retry the same native intent and deliver the old completion late. The fresh trial/reuse consumer resolves one accepted realization set for that intent, counts no extra independent replicate, and preserves failed/unknown attempts and selection effects. Qualified pure replay/replacement progresses without a generic human gate; an explicit new replicate has a distinct basis and declared dependence. Remove intent-to-realization/result binding but retain seed, retry and artifact markers: double counting or silent substitution must fail the discriminator.

- A mixed structural/parameter problem produces actual trials and a fresh-reader Pareto/model-sensitive set. Conflicting objectives retain tradeoffs; a two-intervention joint effect changes ranking/feasibility compared with isolated evaluation.
- Wrong units, stale objective direction, impossible categories, high-score infeasible designs, missing required model completions and ungrounded weights cannot produce a feasible/robust winner. Provider-client presence alone cannot label a deterministic seed LLM-generated.
- Remove real trial/joint-evaluation calls while retaining scores/certificates: consumer/oracle fails. Remove one required model completion: robust result becomes incomplete.

**Входы и ограничения:**

- Native simulation/method contracts; selected objective/value basis. External weights or law are required only for claims that depend on them; retain set-valued candidate comparisons without them.

**Не выбранные альтернативы:**

- LLM invents numeric scores: no computation proof.
- Adopt a new universal BO/MCTS service now: duplicate and unmeasured.
- One scalar proxy chooses the social optimum: hides value choices.

**Поверхность:** Existing frontier/dossier presents per-objective outcomes, feasibility, model dependence, actual cost and bounded search coverage.

**Free-grow / ресурсы:** Method/space/resource registration grows through existing owners. New solver selected only with measured need and compatible assumptions. Outer structure and inner parameter budgets share actual existing permits; no second scheduler.

**Миграция:** Version native artifacts and consumers where needed; legacy provenance/claims are not backfilled as verified. Read old outputs with explicit limits; re-evaluate only actual affected current uses.

**Rollback:** Suspend affected new use; preserve immutable history and legally permitted receipts; revert behavior by a forward repair/version, not history rewrite. Never restore revoked authority or rights.

**Параллельность:** P0-ACCEPT plus interface agreements: DES-02, GYD-30, GYD-31. Actual producer outputs are mandatory for composed acceptance; interfaces do not simulate final evidence. Exact shared paths and semantic owners stay single-writer.

<a id="DES-04"></a>
## DES-04 — Close substantive N6/N7 feedback, acquisition and alternative-retention loop

Extend native N6/N7 bridges so actual failed assumptions, counterexamples, numerical outcomes and missing evidence alter the next candidate or acquisition decision. Preserve existing fronts and declared exploration limits. Historical deferred MCTS/meta/Portfolio machinery is not added as a prerequisite.

**Переиспользовать:** `policy-engine/src/polisyos/runtime/quality/generation_cycle.py@dccea950845cda5b38f026e7770c07819d31f4d9`; `policy-engine/src/polisyos/runtime/quality/recursive_generation_cycle.py@dccea950845cda5b38f026e7770c07819d31f4d9`; `policy-engine/src/polisyos/runtime/quality/acquisition_planner.py@dccea950845cda5b38f026e7770c07819d31f4d9`.

**Шаги:**

1. Resolve N4/N5/N6/N7 ports and their ledger/selection owners, including terminal reasons and actual emitted-set accounting.
2. Bind feedback to the candidate, property, evidence and evaluator that produced it. Send only permitted diagnostic feedback back to proposer; protect sealed confirmation outcomes from tuning.
3. Preserve materially distinct alternatives and candidate-only research/quarantine. Track rejected, unexecuted and resource-truncated branches separately; missing support is not proof that an idea failed.
4. Connect selected data needs to existing CAP/GYD-24 acquisition. Use DEB-13 decision-value output when established, but allow existing justified requirements/rule-bound acquisition when numerical EVSI is unavailable; do not invent a VOI number or impose an all-acquisition EVSI gate.
5. Run a controlled disconfirmation and a targeted acquisition case through persisted cycle state and fresh frontier/decision reader; show the next actual choice changes.

**Композиция и границы:**

- DES-04 is the N6 bridge writer; CAP/GYD-24/DEB-13 keep their mechanisms. Evidence-policy/legal changes use existing LIF invalidation.
- DES-08 may prepare memory interface concurrently; its later history influence is not required for the first within-run loop.

**Acceptance / adversarial / removal:**

- A material counterexample produces a revised mechanism or properly rejected branch; a genuine new input changes a subsequent trial/choice. Under honest budget exhaustion the set and next useful action remain visible.
- Repeated paraphrases cannot appear as exploration; a high proxy/weak grounding candidate stays out of DecisionFront. Full declared input-family coverage cannot stand in for actual emitted/visited coverage.
- Disable the feedback or acquisition-result bridge while retaining histories/front markers: the distinguishing next-choice test fails. Removing grammar fallback exposes lost reachable candidates.

**Входы и ограничения:**

- Actual counterexample or controlled owner output, permitted acquisition inputs and selected budgets. Lack of empirical evidence limits conclusions, not the entire candidate loop.

**Не выбранные альтернативы:**

- Build a second scheduler/controller: duplicates N6.
- Acquire only on numeric EVSI in every case: unnecessary dependence and false abstention.
- Declare search complete at budget cutoff: conflates resource and domain ceilings.

**Поверхность:** Existing Cycle Board/frontier explains actual changes, terminal, research opportunities, costs and omitted branches. Public projections retain their existing boundaries.

**Free-grow / ресурсы:** New conforming feedback/rejection reasons derive from native contracts, with unknowns visible; bounded queues and reference-based history reuse existing permits/cancellation.

**Миграция:** Version native artifacts and consumers where needed; legacy provenance/claims are not backfilled as verified. Read old outputs with explicit limits; re-evaluate only actual affected current uses.

**Rollback:** Suspend affected new use; preserve immutable history and legally permitted receipts; revert behavior by a forward repair/version, not history rewrite. Never restore revoked authority or rights.

**Параллельность:** P0-ACCEPT plus interface agreements: DES-02, DES-03, GYD-24. Actual producer outputs are mandatory for composed acceptance; interfaces do not simulate final evidence. Exact shared paths and semantic owners stay single-writer.

<a id="DES-05"></a>
## DES-05 — Compose source-bound legal interpretations into policy-design branches

Extend the existing Lex/NormPack and selected Scientist consumer with versioned multi-norm interpretation branches. Reuse provision/reference extraction and relation verification; synthesize exceptions, definitions, transitions, delegation and competing readings as candidates. Separate current-law admissibility from proposed-law amendment design. No second legal knowledge store or universal jurisdiction precedence table.

**Переиспользовать:** `policy-engine/src/polisyos/lex/normpack/applicability.py@dccea950845cda5b38f026e7770c07819d31f4d9`; `policy-engine/src/polisyos/lex/normpack/conflict_check.py@dccea950845cda5b38f026e7770c07819d31f4d9`; `policy-engine/src/polisyos/lex/interventions/compiler.py@dccea950845cda5b38f026e7770c07819d31f4d9`; `policy-engine/src/polisyos/data_forge/domains/legal/batch/consistency_checker.py@dccea950845cda5b38f026e7770c07819d31f4d9`.

**Шаги:**

1. Census exact accepted legal relation, NormPack/conflict and intervention-map owners. CAP-05 owns source/relation proof; CNT-04 supplies actual case sources and competence/review inputs; DES-05 owns this generic synthesis/consumer delta.
2. Represent branch premises, support and counterevidence spans, source/version/language, distinct legal-valid/effective time, source observation/receipt/verification time, and analysis/knowledge as-of, unresolved links, derivation provenance and affected design refs. Extend native artifacts first; add a small typed artifact only if existing contracts cannot preserve competing branches.
3. Keep malformed/unknown time distinct from truly open effective interval. Re-evaluate latest-only, hardcoded jurisdiction and pairwise conflict shortcuts on selected source; explicit exceptions and transitions can defeat apparent conflicts.
4. Route each materially supported reading to candidate generation and existing legal checks; unknown/contested readings may support declared hypothetical branches, not hard authority gates. A design requiring changed law can generate a clearly not-enacted amendment proposal.
5. Join source/translation/review changes to existing dependency/invalidation owners and fresh document/design consumers. Review profiles resolve independently computable facts; competent external interpretation/acts are required only for the claims that genuinely need them.

**Композиция и границы:**

- CAP-05 retains source-relation producer; DES-05 owns generic interpretation composition in native Lex and the commissioned design adapter; CNT-04 no shared source writes. CNT-08 compares bases; CNT-09 composes selected real case.
- DES-06 consumes branch artifacts, never reinterprets law independently. Shared legal files/schema changes have one exact-path writer.

**Acceptance / adversarial / removal:**

- A selected multi-provision case with reference, exception and transition changes design/limitations across legal dates or readings. A lawful amendment-design branch survives current-law incompatibility while its present-tense authority claim remains refused.
- Retrieved text is not entailment; fake citation, omitted exception, conflicting translation, wrong jurisdiction, invalid end date and asserted precedence cannot produce verified current permission. Do not fabricate ambiguity on unambiguous cases or a single winner where genuine disagreement remains.
- Remove the exception/source binding or branch-to-design bridge while keeping citation/count/status fields: affected consumer must change/refuse; omit change subscription and the stale-projection probe fails.

**Входы и ограничения:**

- Selected official/source relation evidence via CAP-05; CNT-04 case corpus and applicable interpretation/competence evidence. Unknown authority permits declared hypothetical analysis, not enacted-law claims.

**Не выбранные альтернативы:**

- Assign all source engineering to CNT-04: that task owns case data/config, not shared runtime source.
- Make LLM consensus a binding reading: authority laundering.
- Reject every option inconsistent with current law: loses legitimate amendment design.

**Поверхность:** Private legal-branch comparison and candidate policy text with support/contrary spans, current-vs-proposed law and explicit unresolved matters; permitted CNT-09 projections.

**Free-grow / ресурсы:** Extend relation/grammar profiles and jurisdiction/source mappings without closed policy templates. Cross-reference worklist is bounded with explicit unresolved frontier; token limits cannot claim corpus completeness.

**Миграция:** Version native artifacts and consumers where needed; legacy provenance/claims are not backfilled as verified. Read old outputs with explicit limits; re-evaluate only actual affected current uses.

**Rollback:** Suspend affected new use; preserve immutable history and legally permitted receipts; revert behavior by a forward repair/version, not history rewrite. Never restore revoked authority or rights.

**Параллельность:** P0-ACCEPT plus interface agreements: CAP-05, CNT-04, DES-02. Actual producer outputs are mandatory for composed acceptance; interfaces do not simulate final evidence. Exact shared paths and semantic owners stay single-writer.

**Root review refinement:** Current-law permission requires actual CAP-05 emitted, content-bound relation/applicability evidence through the relevant native verifier, not an agreed interface or citation marker. Its absence leaves that conclusion limited/refused while hypothetical/amendment branches remain available. Separate legal-valid time, observed/received/verified time and analysis/knowledge as-of; late correction of earlier effectivity preserves historical knowledge replay and invalidates affected current uses.

<a id="DES-06"></a>
## DES-06 — Author useful policy-document packages with exact semantic bindings

Extend native PolicyArtifactBundle/BureaucraticDocument rendering to author source-bound candidate policy documents: options paper, draft provisions, explanation, impact and monitoring materials as selected profiles, not closed domain templates. Each material statement/table cell binds its semantic role and exact candidate/claim/metric/provision; LLM prose does not become an authority source.

**Переиспользовать:** `policy-engine/src/polisyos/scientist/policy_design/output.py@dccea950845cda5b38f026e7770c07819d31f4d9`; `policy-engine/src/polisyos/runtime/http/services/bureaucratic_rendering.py@dccea950845cda5b38f026e7770c07819d31f4d9`; `policy-engine/src/polisyos/core/contracts/runtime.py@dccea950845cda5b38f026e7770c07819d31f4d9`.

**Шаги:**

1. Agree DES-06/07 shared versioned document and edit interface before source work. Reuse existing render/export routes and authoring UI owner; keep G6 PUBLIC restriction and UI-02 data-only practice unchanged.
2. Join policy design, selected law/evidence and quantities by immutable refs/profile. Bind stable semantic span/cell IDs, source versions, metric/units/population/period/uncertainty, proposed-vs-current legal role, audience/purpose and revision.
3. Produce coherent linked documents: action, rationale, alternatives/no-op, affected groups, distribution, cost, feasibility, uncertainty/dissent, implementation prerequisites and monitoring. Missing inputs remain visible; examples of genres do not limit mechanisms.
4. Persist candidate draft/revision and expose it through authorized private/reviewer/expert native API/UI. Add a real editable DOCX carrier with semantic sidecar/stable IDs where feasible and truthful unsupported-feature loss records; verify parsing in an independent reader. A JSON/HTML source packet is not DOCX.
5. Use exact native numbers and recomputable transformations. Reconcile cross-document/table references; enroll law/source/rights changes so current rendered passages become stale/limited and require re-evaluation.

**Композиция и границы:**

- A historical erased parent does not by itself forbid every retained derivative. A permitted retained assessment/model/result may support its qualified use if its own retention, current-use rights and sufficient verification basis survive. Recomputations or claims needing the missing raw basis remain unavailable; a receipt, hash or displayed number alone cannot establish that sufficient basis. Apply LIF-05/LIF-07 to the actual use/dependency relation, including any valid derivative-specific rule, and retain only allowed identifiers and replay limitations. No revived old head, invented raw replay or permission to reconstruct erased input.

- DES-06 writes document producer/schema/export, DES-07 imports/edits through shared interface; one document/schema writer per cut. UI-05 is intake, not document owner.
- Independent bounded fixtures permit producer preparation. Composed packet includes DES-01/02/03/04/05 outputs only when selected; no blanket wait for every legal/learning task. CNT-09 consumes the selected real case.

**Acceptance / adversarial / removal:**

- After verified lawful raw erasure, a separately permitted and sufficiently verified retained result supports its selected historical/derivative use with explicit replay limits. A raw-dependent recomputation or unpermitted new purpose remains refused/limited; a mere receipt is insufficient. Remove actual dependency/current-use qualification while retaining erasure and result markers: both blanket false refusal and unsupported admission are detected.

- A fresh consumer opens a substantive options/proposed-measure/explanation set, traces material claims and recomputes selected numerical derivations where their required basis is available and permitted; otherwise it verifies the permitted retained result/receipt through its sufficient bound evidence, displays replay limits, and refuses only uses requiring the unavailable basis; an independent actual DOCX reader can read its text/tables/roles. A new format profile preserves the same semantic basis without central domain-code changes.
- Unsupported assertions stay marked proposals; missing qualifications, changed denominator/rounding, invented legal act, counterfeit DOCX and audience/rights mismatch cannot produce a trusted view. A document genre is not mandate or enactment.
- Remove evidence/quantity/status binding but keep citations and watermark: fidelity checks fail. Replace real DOCX bytes with HTML-in-JSON while keeping MIME/name: format proof fails.

**Входы и ограничения:**

- Selected packet and allowed document audience; native numerical/legal suppliers only for chosen claims. Form/language profile and reader-study participants for usability claims, not for mechanical source binding.

**Не выбранные альтернативы:**

- Use a report template with free text only: loses semantic links.
- Treat every draft paragraph as a verified claim: kills exploratory drafting.
- Publish via G6 or UI-02 data-only route: violates existing boundary.

**Поверхность:** Authorized private/REVIEWER/EXPERT editor/view, actual document exports and MACHINE/audit refs. Public prose release is outside this initial route and needs its separately ratified projection; UI-02 alone supplies no such permission.

**Free-grow / ресурсы:** Language/jurisdiction/presentation profiles add formats over shared semantic facets. New semantic role requires native schema/consumer migration; no promise arbitrary prose can be fully formalized. Stream/reference large annexes.

**Миграция:** Version native artifacts and consumers where needed; legacy provenance/claims are not backfilled as verified. Read old outputs with explicit limits; re-evaluate only actual affected current uses.

**Rollback:** Suspend affected new use; preserve immutable history and legally permitted receipts; revert behavior by a forward repair/version, not history rewrite. Never restore revoked authority or rights.

**Параллельность:** P0-ACCEPT and complete scoped rebind; independent preparation. Actual producer outputs are mandatory for composed acceptance; interfaces do not simulate final evidence. Exact shared paths and semantic owners stay single-writer.

**Root review refinement:** Bind actual displayed/exported DOCX paragraphs and cells to the semantic sidecar and exact revision. Independently change a sentence/cell while keeping IDs and old sidecar: fresh reader must detect unbound/stale meaning and reject inherited support. Independent format parsing alone is insufficient.

<a id="DES-07"></a>
## DES-07 — Round-trip human document edits into design and evidence re-evaluation

Add revision/import/edit bridges to the same document owner. Preserve human-authored bytes or exact permitted references and immutable parentage only under existing storage/processing/retention rights, align stable AST/span/cell IDs first, and interpret semantic deltas as candidate patches to native design/method/legal owners. Ambiguity is explicit; a hash or second LLM does not prove arbitrary prose equivalence.

**Переиспользовать:** `policy-engine/src/polisyos/runtime/http/services/bureaucratic_rendering.py@dccea950845cda5b38f026e7770c07819d31f4d9`; `policy-engine/src/polisyos/runtime/http/routes/artifacts.py@dccea950845cda5b38f026e7770c07819d31f4d9`; `policy-engine/src/polisyos/core/contracts/runtime.py@dccea950845cda5b38f026e7770c07819d31f4d9`.

**Шаги:**

1. Freeze the common revision/alignment/interface with DES-06 at interface stage; split importer/UX files while shared AST/schema remains one writer. Existing document profile/permission rules apply on every import.
2. Handle controlled-editor changes and offline editable DOCX reimport, including lost IDs, moved tables, tracked changes, annotations and newly inserted clauses. Unsupported features are preserved/reported; unbound text never inherits old verification.
3. Route parameter/population/mechanism changes to search/evaluation, factual/legal changes to their owners, and value/goals to explicit alternative or authorized selection. Even a prose-only rewrite rechecks material entailment; it cannot erase qualifiers by classification.
4. Use expected-base revision/CAS semantics for concurrent edits; conflict creates branch/reconciliation, never last-writer truth. Select affected dependency closure for recomputation and regenerate linked materials without overwriting human text silently.
5. Persist accepted mappings, unresolved edits, re-evaluations and supersession; fresh readers show exactly which revised statements are supported, stale, proposed or unbound.

**Композиция и границы:**

- DES-06/07 share one schema; agreement permits parallel preparation, completed render implementation is not required first. Existing LIF/currentness and native owners recompute actual semantics.
- Canonical semantic nodes stay native; free prose remains text with scoped mapping, not forced into an invented universal AST of all law.

**Acceptance / adversarial / removal:**

- A threshold edit changes the native numerical trial and table; a new exception changes legal/design comparison; a mechanism edit creates a new candidate. Reimport with stripped IDs preserves text as unbound rather than falsely equivalent.
- Concurrently edited base, renamed target, copied citation with changed assertion, injected macros/external relationships, removed uncertainty and reordered paragraphs cannot silently inherit prior status or execute imported content.
- Disable edit→owner dispatch or conflict detection while keeping revision IDs: fresh recomputation/concurrency probe fails. Hash-only semantic equivalence must be falsified by a changed material clause.

**Входы и ограничения:**

- Actual edited carrier or UI revision; explicit human mapping/choice only for materially ambiguous edits. The system itself supplies deterministic alignment and recomputation wherever possible.

**Не выбранные альтернативы:**

- Require every edit be fully formalized before saving: destroys useful human drafting.
- Treat byte round-trip as semantic round-trip: proxy proof.
- Fork a separate document truth database: contradicts source custody.

**Поверхность:** Private authorized human editor/import/revision diff with explicit map, unresolved changes, affected computations and unchanged historical versions; no institutional submission workflow.

**Free-grow / ресурсы:** New supported carrier/profile extends existing import/render adapters; no new product workflow for each domain. Bound parse/unpack, no macros/network fetch; use existing process resource/rights gates.

**Миграция:** Version native artifacts and consumers where needed; legacy provenance/claims are not backfilled as verified. Read old outputs with explicit limits; re-evaluate only actual affected current uses.

**Rollback:** Suspend affected new use; preserve immutable history and legally permitted receipts; revert behavior by a forward repair/version, not history rewrite. Never restore revoked authority or rights.

**Параллельность:** P0-ACCEPT plus interface agreements: DES-06. Actual producer outputs are mandatory for composed acceptance; interfaces do not simulate final evidence. Exact shared paths and semantic owners stay single-writer.

**Root review refinement:** Normal import, history, processing and export obey existing LIF-05 rights/retention, not just rollback. Revocation/expiry with intact revision IDs must prevent prohibited copy/use/egress and retain only permitted custody receipts. Sidecar alignment does not supersede actual edited carrier content.

<a id="DES-08"></a>
## DES-08 — Make cross-run experience change search without laundering evidence

Wire existing LessonRegistry, balanced retrieval, transfer/Pareto seeds and hypothesis ledger into later candidate generation and strategy selection. Separate actual evaluated success/failure/opportunity lessons from prior LLM hypotheses. Preserve the native ban on active influence modes for LLM-origin BalancedMemory; candidate hypotheses use their existing candidate-only envelope, not a bypass of that ban.

**Переиспользовать:** `policy-engine/src/polisyos/scientist/policy_design/search.py@dccea950845cda5b38f026e7770c07819d31f4d9`; `policy-engine/src/polisyos/scientist/methods/search/lessons.py@dccea950845cda5b38f026e7770c07819d31f4d9`; `policy-engine/src/polisyos/scientist/orchestration/memory/retrieval.py@dccea950845cda5b38f026e7770c07819d31f4d9`; `policy-engine/src/polisyos/scientist/orchestration/memory/balanced.py@dccea950845cda5b38f026e7770c07819d31f4d9`.

**Шаги:**

1. Trace actual persistence and retrieval consumers on accepted source. Reuse existing CAS/index/query owners; inject durable sink where the selected formulator still defaults to memory only.
2. Record actual run/candidate/evaluator outcome, preconditions, scope/units/model/rule, exposure/selection, resource cost and rights. Unexecuted alternatives and textual reflection are not failed/successful experiments.
3. Retrieve before proposal generation using applicability/expiry/revocation/contamination checks. Pass allowed native lessons and separately typed hypothesis refs to the proposer; persist selected/rejected influence and downstream candidate change.
4. Preserve balanced successes, failures and opportunities; test negative transfer and suppression of novel alternatives. Do not let memory similarity substitute for current data, law, effect evidence or mandate.
5. Connect LIF-07 revocation and future-use invalidation. Evaluate transfer with memory-off and chronology/source-disjoint tasks; old closed replay remains on its original basis.

**Композиция и границы:**

- DES-08 and DES-03 share search.py writer; DES-08 owns retrieval adapter, not numerical evaluator. LIF-07 owns influence lineage/cascade.
- DES-10 measures transfer quality; GYD-25 retains retrieval adequacy, which does not by itself establish transfer utility.

**Acceptance / adversarial / removal:**

- A later task actually changes a candidate or search choice using a compatible evaluated lesson; fresh-process retrieval resolves exact refs. A useful opportunity survives failure-heavy memory, with actual cost/benefit measured separately.
- Wrong population/unit/jurisdiction/objective/model generation, revoked rights, fake success, held-out contamination or LLM reflection cannot enter an evaluated-evidence lane. Candidate memory cannot mutate O1 posterior or O3 world.
- Remove retrieval while keeping lesson refs: measured controlled influence disappears. Remove persistence: next process cannot see the record. Retain candidate labels but attempt authority use: protected consumer refuses.

**Входы и ограничения:**

- Actual evaluated source runs and reuse rights; candidate-only hypotheses need truthful provenance. Genuine confirmation inputs/activation remain GYD-09/12 obligations, not prerequisites for candidate search learning.

**Не выбранные альтернативы:**

- New memory database: duplicates existing owners.
- All LLM reflections become verified lessons: false learning.
- Wait for all O1/O3 activation before search-memory work: unnecessary dependency.

**Поверхность:** Search-history explanation of chosen/rejected experience, scope, cost and influence; separate O1/O2/O3 learning dashboards and unchanged WP activation.

**Free-grow / ресурсы:** New scoped lessons/methods grow via existing schemas and registry; new interpretation class needs contract review. Bounded retrieval/indexes preserve explicit incomplete frontier and do not preload all history.

**Миграция:** Version native artifacts and consumers where needed; legacy provenance/claims are not backfilled as verified. Read old outputs with explicit limits; re-evaluate only actual affected current uses.

**Rollback:** Suspend affected new use; preserve immutable history and legally permitted receipts; revert behavior by a forward repair/version, not history rewrite. Never restore revoked authority or rights.

**Параллельность:** P0-ACCEPT plus interface agreements: LIF-07, DES-04. Actual producer outputs are mandatory for composed acceptance; interfaces do not simulate final evidence. Exact shared paths and semantic owners stay single-writer.

**Canonical writer allocation:** DES-08 owns retrieval adapter; durable formulator sink delta is sent to DES-01 and hypothesis binding to DES-02. It does not acquire their shared file writes.

<a id="DES-09"></a>
## DES-09 — Bind real LLM execution, contextual evidence and resource use to native ledgers

Reuse existing traced gateway, prompt/tool ledger and resource owners for all selected generation, critique, legal and document calls. Bind actual input/context selection and allowed output to provider/model/profile, tools, parent artifacts, rights, purpose, time and cost. A connection, provider name, schema-valid answer or second model vote is not invocation, usefulness or authority.

**Переиспользовать:** `policy-engine/src/polisyos/runtime/quality/prompt_tool_ledger.py@dccea950845cda5b38f026e7770c07819d31f4d9`; `policy-engine/src/polisyos/runtime/quality/hypothesis_ledger.py@dccea950845cda5b38f026e7770c07819d31f4d9`; `policy-engine/src/polisyos/scientist/policy_design/formulator.py@dccea950845cda5b38f026e7770c07819d31f4d9`.

**Шаги:**

1. Identify canonical gateway caller and existing budget/cancellation/egress owners. DES-09 writes only shared invocation/context projection; consumer tasks own their domain semantics.
2. Build bounded retrieval/context with exact source and selection refs, source-language/version and preserved counterevidence or explicit omissions. Summaries remain derived candidates; verify material exceptions lost during compression and context-position changes.
3. Persist permitted inputs/output refs, tool choices, source lineage, actual role in the candidate and usage. Protect secrets and restricted prompts in artifacts/logs; no requirement to collect hidden model chain-of-thought.
4. Distinguish recorded-response reconstruction, deterministic replay and fresh stochastic live runs. Bind exposed provider version/settings/seed; unknown provider internals or unstable versions limit reproducibility rather than fabricated certainty.
5. Test timeout/retry/cancel/partial streams, provider changes and cache hits under existing OPS/CAP/LIF contracts. Cached content cannot be reused across incompatible rights/epoch/model/purpose; deterministic fallback is truthfully labelled.

**Композиция и границы:**

- DES-02/05/06/08 consume shared invocation contract, not new gate semantics. OPS-07/CAP/LIF retain permits, egress and lifecycle.
- Interface agreement enables producer preparation; real external calls require actual rights and compute permits. No source code execution from model text through G6.

**Acceptance / adversarial / removal:**

- A permitted real call is traceable through selected context to a persisted candidate and actual usage; recorded replay is separately labelled. Missing-provider mode preserves allowed existing grammar work without fabricated live evidence.
- Context injection, private-query exfiltration, provider drift, stale cache, lost legal exception and client-without-call fail their actual property checks. Removing a qualifier during summarization cannot produce a stronger claim.
- Stub out actual invocation or strip decisive context while retaining ledger/model markers: provenance/semantic tests detect the change. Cancelled work cannot retain phantom successful call/result.

**Входы и ограничения:**

- Permitted provider access/credentials and selected model profile for live proof. Existing rights/cost owners supply authorization; missing internal connector or adapter is assigned engineering, not external authority.

**Не выбранные альтернативы:**

- New LLM orchestration/budget service: duplicate owners.
- Store every raw prompt/output forever: rights and storage failure.
- Require exact stochastic prose replay: false guarantee.

**Поверхность:** Authorized operational/audit view of model/context/selection/version/cost and replay limitations; sensitive content only under existing rights, safe public summaries only where already admitted.

**Free-grow / ресурсы:** Provider/model/tool profiles extend existing gateway interfaces; new protocol needs bounded adapter, not copied domain logic. Bound context/token/retrieval resources and use purpose-scoped caches.

**Миграция:** Version native artifacts and consumers where needed; legacy provenance/claims are not backfilled as verified. Read old outputs with explicit limits; re-evaluate only actual affected current uses.

**Rollback:** Suspend affected new use; preserve immutable history and legally permitted receipts; revert behavior by a forward repair/version, not history rewrite. Never restore revoked authority or rights.

**Параллельность:** P0-ACCEPT plus interface agreements: LIF-05, OPS-07. Actual producer outputs are mandatory for composed acceptance; interfaces do not simulate final evidence. Exact shared paths and semantic owners stay single-writer.

**Canonical writer allocation:** DES-09 owns prompt_tool_ledger.py and the exact existing gateway/context projection path resolved at P0. formulator.py and hypothesis_ledger.py are read-only suppliers: submit interface requests to DES-01 and DES-02 respectively. No alternate spelling of their lease creates an independent writer.

<a id="DES-10"></a>
## DES-10 — Verify productive search, learning and readable policy outputs with independent comparisons

Extend existing GY V2/V3/V5/V7 and D3 benchmark consumers with a separate productive-capability comparison. Prepare the frozen corpus, independent semantics/oracles and method before freeze; execute the composed comparison in the single FINAL-REPLAY wave. Safety refusals, schema validity, fluent prose and retrieval hits do not demonstrate useful design or learning.

**Переиспользовать:** `policy-engine/src/polisyos/runtime/quality/design_generation.py@dccea950845cda5b38f026e7770c07819d31f4d9`; `policy-engine/src/polisyos/runtime/quality/generation_cycle.py@dccea950845cda5b38f026e7770c07819d31f4d9`.

**Шаги:**

1. Bind each R14 obligation to the accepted real producer/consumer and exact case, source/input/backend/model/profile identity. Reuse original V1–V7 oracles without reducing their criteria; allocate this separate evaluation slice.
2. Predeclare controlled known-solvable, ambiguous, ungroundable, multilingual, shifted-domain and unseen conforming-resource cases. Keep development data apart from final holdouts/exposure; reserve real independent audiences/reviewers for claims that need them.
3. Compare grammar/deterministic baseline, hybrid and selected LLM/memory/feedback ablations with equal resource ceilings and actual spend. Include current-policy/no-intervention comparator; do not waste budget to equalize actual use.
4. Measure semantic diversity, feasible/nondominated coverage, false abstention, numerical correctness, source/status fidelity, legal exception/branch coverage, transfer harm/benefit, document comprehension and cost. Freeze relevant thresholds/oracles before results; never optimize useful_design_rate or substitute metrics for promotion.
5. Report complete cases/arms/seeds/errors/exclusions, case-clustered uncertainty and judge disagreement/bias. Separate engineering success, live-provider usefulness, real-reader usability and authentic domain/effect claims. If external participants unavailable, preserve that specific result UNRUN and finish internal mechanisms.
6. Run after FINAL-REVIEW, joining actual outputs at FINAL-REPLAY; one replay identity, exact resource permits and independent review. Changes invalidate only affected proof; no repeated global wave for local preparation.

**Композиция и границы:**

- DES-10 owns comparison preparation/execution join, not a new search engine or all original GY verification. GYD-17/18/20/22/25/26 and CNT-09 provide their named existing scopes.
- owner_readiness = reviewed recipe/oracles/local verifier checks; full comparison remains UNRUN until FINAL-REPLAY. Actual live results and all declared required endpoints join FINAL-USE disposition.

**Acceptance / adversarial / removal:**

- A known-solvable real path produces material alternatives and a coherent document; all-abstain/all-no-op implementations cannot pass. Selected equal-ceiling comparisons report useful and harmful/null outcomes without universal superiority claims.
- Paraphrase inflation, invented model invocation, self-scored novelty, omitted failed arms, contaminated holdout, prompt-position legal exception loss, copied citations, unsupported enacted-law prose and hidden subgroup failures are caught. Unavailable live/audience inputs never become simulated authentic PASS.
- Remove generation, retrieval/feedback, numerical execution, source binding or document edit bridge one at a time but keep report markers; the corresponding actual endpoint fails or loses its measured effect.

**Входы и ограничения:**

- Internal frozen cases and exact real-path suppliers; lawful live model access, selected independent reviewers/target readers and legitimate domain inputs for their respective claims. Sample size insufficient for superiority yields descriptive evidence.

**Не выбранные альтернативы:**

- Only negative guards: permits a safely useless system.
- Single LLM judge or scalar score: hides bias/value choices.
- Run broad replay before final source review: re-prices expensive verification.

**Поверхность:** Reviewer/expert quality report resolving each candidate/case/evaluator/trace and limitations; GYD-22 consumes diagnostics. No authority is conferred by benchmark score.

**Free-grow / ресурсы:** Derive cases/method/resource sets from selected native contracts with newly registered-resource tests. Extend evaluation dimensions with declared oracles; no hardcoded universal policy benchmark or claimed exhaustive domain coverage.

**Миграция:** Version native artifacts and consumers where needed; legacy provenance/claims are not backfilled as verified. Read old outputs with explicit limits; re-evaluate only actual affected current uses.

**Rollback:** Suspend affected new use; preserve immutable history and legally permitted receipts; revert behavior by a forward repair/version, not history rewrite. Never restore revoked authority or rights.

**Параллельность:** P0-ACCEPT and complete scoped rebind; independent preparation. Actual producer outputs are mandatory for composed acceptance; interfaces do not simulate final evidence. Exact shared paths and semantic owners stay single-writer.

**Root review refinement:** Freeze a decision-relevant positive criterion, independently labelled, for designated known-solvable controls: a candidate answers the declared decision need or a specific acquisition/evidence path resolves it. Feasible diverse but irrelevant alternatives must not pass this criterion. All-null decision-support outcomes leave productive capability not_established even if plumbing passes. This is a bounded acceptance discriminator, never a useful_design_rate optimization/reward/promotion target. No-op and deliberate removal arms are comparators expected to fail productivity, not implementations required to produce an intervention. Reviewer panels belong to evaluation, not per-run/manual authority gates.

<a id="extensions"></a>
## Дополнения существующих задач

Исходные поля/критерии сохраняются. Этот additive delta обязателен вместе с исходной карточкой; не заменяет первоначальную приёмку.

| Task | Дополнение |
|---|---|
| CAP-05 | Keep candidate extracted legal relations separate from verified relations; preserve source span/version, language, cross-reference alternatives and legal time roles. Supply DES-05 via the existing relation owner; do not duplicate interpretation synthesis. |
| CNT-04 | Supply selected multi-provision case sources, exceptions/transition/competence and appropriate review inputs for DES-05. This remains a content/data/config lane; DES-05 owns generic Lex/Scientist source delta. Preserve current law versus proposed amendment. |
| CNT-08 | Compare DES-05 interpretation branches and DES-08 influence lineage when selected; preserve disagreement, source dependence and no automatic current authority from history. |
| CNT-09 | For selected substantive-design case, consume actual DES alternative, legal and document artifacts; prove changed premise changes the design/document. Authentic commissioning remains separate from controlled positive proof. |
| GYD-30 | Supply actual joint simulation/composition evidence to DES-03. Add an individually/pairwise plausible but jointly divergent case, keeping K_sim distinct from K_world; do not build a search controller here. |
| GYD-31 | Preserve vector/set-valued objectives and model-sensitive/incomparable choices in DES-03/06; no implicit social weights or scalar promotion winner. |
| GYD-23 | R14 richer N4/N6 search does not alter this Slice0 BIND/ESTIMATE/VERIFY scope or terminal. DEB-13 EVSI and DES-04 use existing compatible interfaces only; do not introduce a blanket numeric-EVSI requirement. |
| GYD-33 | Check the meaning of emitted versus available instrument_family_coverage against actual selected S2 emissions. Preserve S2 bounded one-candidate scope; names/menu membership are not measured emitted coverage. |
| GYD-17 | Share exact real producer/consumer replay identity with DES-10; original V2 criterion remains independently mandatory. |
| GYD-18 | Share full frozen case denominator and distinct-domain strata with DES-10; do not mix candidates/seeds with independent case count. |
| GYD-20 | Distinguish recorded LLM response reconstruction from fresh live stochastic behavior and deterministic numeric replay. Unknown provider version limits the claim. |
| GYD-22 | Read DES-10 productive quality, diversity, cost and false-abstention diagnostics without using useful_design_rate as promotion objective. |
| GYD-25 | Retain original retrieval adequacy; DES-10 adds separate downstream semantic diversity/transfer evaluation. Retrieval hits alone do not demonstrate learning. |
| GYD-26 | Judge output binding proves identity only. DES-10 tests order/verbosity/provider bias and independent agreement; LLM judge consensus never authorizes. |
| LIF-07 | Track actual candidate/memory/context influence and selection exposure for DES-08/09; revoked/stale history cannot remain active by copied summaries. Preserve original closed replay. |
| LIF-05 | Apply existing rights/retention/restore rules to LLM context, caches and document revisions; do not introduce perpetual prompt storage. |
| OPS-07 | Reuse existing permits, costs, cancellation and resource accounting for model calls, numeric trials and document re-evaluation; no independent DES budget ledger. |
| UI-05 | Pass exact framing/unknowns to DES-01 and show authorized candidate references. G6 remains bounded intake; PUBLIC raw recommendation text remains out of scope. |
| UI-02 | Data-only public practice remains unchanged. DES-06/07 private document drafting/export does not acquire public prose permission through this task. |
| DEB-10 | Where selected, independent print/accessibility/readability checks cover actual DES-06 document carrier; content-type or HTML preview does not prove DOCX fidelity. |
| DEB-13 | Expose established gross/net EVSI distinctly to DES-04 when selected. Unsupported EVSI remains limited; other native justified acquisition routes continue without fabricated numeric ranking. |
| FINAL-FREEZE | Include DES mechanism readiness and DES-10 reviewed comparison preparation; do not require final live/audience comparison to satisfy its own freeze predecessor. |
| FINAL-REPLAY | Execute DES-10 in this same frozen wave; join actual R14 obligations separately from unchanged original GY/Atlas/debt/R9 outcomes. |
| FINAL-USE | In addition to original programme obligations, reconcile every R14 capability obligation and selected required quality claim. Unavailable live-model or audience evidence cannot silently disappear. Controlled PASS is not authentic usefulness; explicit competent scope change required for deferral. |
