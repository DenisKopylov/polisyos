# R14 capability audit: substantive search, learning, and documents

**Status:** proposed assurance delta; not product implementation, SDD amendment, or E02 acceptance; the final planning allocation is in tasks.json. Product paths below are relative to `policy-engine/`. Synthesizes the six R14 research notes and draft [architecture/04](../architecture/04-generative-search-learning-and-documents.md).

## Baseline and boundaries

The complete `tasks` array in `tasks.json@c8986d035f12c1c3d9e5d0d57e369fe8257bccbc` was parsed: **109 objects (JSON manifest)**. Relevant rows are allocations, not runtime proof. Code references use `dccea950845cda5b38f026e7770c07819d31f4d9`, an unaccepted static E02 observation.

Historical intent/status is separate: `docs/plans/active/layer3-slices/GY-engine-subordination.md@c8986d035f12c1c3d9e5d0d57e369fe8257bccbc` §Phase 5 defines N4/N6 and §8.5 records them historically executed. Reuse those owners; neither history nor this audit certifies present end-to-end behavior. G2 searches grounded causal claims/methods; G3 finds proof-carrying analytics; G6 frames/routes bounded requests and records tool choices. G6 is not a policy generator or public recommendation surface. UI-05 remains its candidate/refusal/audit consumer. GYD-23 Slice 0 stays BIND/ESTIMATE/VERIFY only, with deterministic `SeedTrajectoryPlanner`, its original stopping point, and no DesignCandidate/agent playbook. Full MCTS, meta-controller, and portfolio machinery remain deferred.

The target `policy-design-search-target-spec.md@c8986d035f12c1c3d9e5d0d57e369fe8257bccbc` (`RACE-HOG-PODS`; SDD-B02 qualifies substrate examples) requires optimistic search/conservative promotion, separate uncertainty types, and “Proposer proposes, Surrogate prioritizes, Validator certifies.” Universal-vision Rules 1/2/5/12 in `universal-policy-design-system-vision-and-organizing-rules.md@c8986d035f12c1c3d9e5d0d57e369fe8257bccbc` require grounding, candidate-only generation, no useful-rate promotion target, and free-growth grammar/registries. Candidate research may carry declared unknowns; execution, protected claims, promotion, and publication retain their admission gates.

The `DES-01`–`DES-10` labels below are ten new planned engineering task objects, added to the baseline 109. Each extends native owners; none creates a parallel search, legal, memory, document, or VOI service. Capability labels apply only to the named path/property.

## Findings

### R14-F01 — Request framing to N4 (DES-01)

**Evidence/coverage:** G6 `runtime/quality/proving_ground/bounded_request_agent.py@dccea950845cda5b38f026e7770c07819d31f4d9:1439-1457,1916-2033` already emits bounded request/candidate frames and selected/rejected choices; UI-05 owns the candidate/refusal Clerk and audit path.

**Bounded gap/proposal:** no explicit task proves alternative framings, assumptions, and an unknown mandate survive the G6-to-N4 edge with the chosen framing recorded. Extend the existing frame and orchestration contract; do not add generation or tool rights to G6. **Allocation gap:** no explicit complete proof of this edge in the baseline task contract. Actual bridge absence is not_established until caller census; G6 producer exists. Allocate real-path semantic verification, and bridge repair only if needed.

**Falsifier:** one request with two materially different interpretations and unknown mandate must preserve both as candidates and pass the unknown to N4. Remove the branch/loss binding but retain prompt/frame IDs; fresh consumer must lose that claim.

### R14-F02 — N4 qualitative mechanisms and open grammar (DES-02)

**Evidence/coverage:** `runtime/quality/design_generation.py@dccea950845cda5b38f026e7770c07819d31f4d9:219-327,1019-1044,2284-2351,4639-4647` has real drafter/formalizer/critic organs, typed shadow candidates/atoms, provenance, three-candidate request, and structural diversity report. `generation_cycle.py@dccea950845cda5b38f026e7770c07819d31f4d9:1933-1954,3356-3455` has N6 fronts and N4 port. GYD-25/30/31/32/33 cover retrieval, joint composition, values, substrate, and knowledge binding.

**Bounded gap/proposal:** structural keys do not prove semantic diversity, and candidate typed output does not prove an N4-to-N6 set was persisted and read by a fresh consumer. Extend N4 grammar/proposal path to retain distinct intervention/cause hypotheses; keep ideas not yet compilable as unbound candidates with lost meaning and needed facet, not silently erase or execute them. New registered resources must be discoverable without a hard-coded template. **Labels:** `semantic_test_missing`; persisted N4→N6 bridge completeness not_established from the inspected return/port alone; repair only after accepted-source census. N4 producer is present.

**Falsifier:** paraphrases collapse; same words with different operator/target/effect/counterfactual structure remain distinct; a registered new construct reaches candidate validation without search-code edits. Removing the actual proposal call while keeping IDs fails.

### R14-F03 — Truthful hybrid and numeric search (DES-03)

**Evidence/coverage:** Scientist `policy_design/search.py@dccea950845cda5b38f026e7770c07819d31f4d9:249-390,472-558,652-684` already provides structure→parameter→narrative and multiobjective Bayesian search. Stage B `run_hierarchical_policy_search.py@dccea950845cda5b38f026e7770c07819d31f4d9:1081-1187` compiles, checks readiness/counterfactuals, simulates, and evaluates. Concrete P38: `_hybrid_seed_candidates` (`policy_design/search.py@dccea950845cda5b38f026e7770c07819d31f4d9:852-901`) sets `hybrid_seed_llm_assisted` from client presence but makes no LLM call; emitted variants are deterministic.

**Bounded gap/proposal:** native numeric/simulation owners exist, but that seed’s provenance is false and no allocated acceptance proves an actual structural-proposal→numeric-trial chain. Extend the Scientist coordinator: LLM may propose mechanisms/methods/spaces/starts; native optimizers run bounded typed trials and return actual units, assumptions, uncertainty, and spend. Remove/repair the seed label based on invocation provenance. GYD-30 first resolves its certificate owner; DEB-13 owns its metric producer; GYD-23 keeps the SearchLedger writer. **Labels:** localized `producer_missing` for the invocation that the seed label claims; `verification_missing`, `semantic_test_missing` for the hybrid claim.

**Falsifier:** configured gateway/no call cannot pass as LLM-generated; removing a call while retaining markers turns the gate red. Compare grammar, actual LLM proposal, and hybrid under equal maximum resources; malformed or infeasible categorical candidates never reach Stage B.

### R14-F04 — N6 feedback changes the next proposal (DES-04)

**Evidence/coverage:** N6 already has Decision/Research/Quarantine/Portfolio fronts and N4 port (`generation_cycle.py@dccea950845cda5b38f026e7770c07819d31f4d9:1933-1954,3356-3455`). GYD-17/18/19/20/21/22 cover real-loop proof, distributions, firewall, replay, validation, and health signals; GYD-30 covers joint composition.

**Bounded gap/proposal:** these adjacent tasks do not make feedback-driven multi-proposal change an acceptance endpoint. Extend N6/N7 to consume a real counterexample, trial, incompatibility, or missing basis and preserve selected/rejected/unexecuted alternatives with reasons. Reuse current fronts/ledger; add no controller or full MCTS. **Label:** `semantic_test_missing`; rebind the caller before claiming any more missing chain elements.

**Falsifier:** hold initial proposals fixed and change a joint counterexample; persisted lineage and fresh readback show the next proposal/front changed. Removing the consumed result while retaining markers fails. Budget exhaustion is not search-space exhaustion.

### R14-F05 — Legal branches consumed by Scientist (DES-05)

**Evidence/coverage:** At the pin, Data Forge Legal `data_forge/domains/legal/batch/reference_extractor.py@dccea950845cda5b38f026e7770c07819d31f4d9` / `reference_resolution.py@dccea950845cda5b38f026e7770c07819d31f4d9` extract provisions/references; Lex `lex/normpack/applicability.py@dccea950845cda5b38f026e7770c07819d31f4d9` scopes versions, and `lex/interventions/compiler.py@dccea950845cda5b38f026e7770c07819d31f4d9` uses `LexProvisionMappingRegistry`. GL mandate search retains unresolved norms `context_only`. These are real owners, not a demonstrated many-norm branch-to-policy-search consumer.

**Ownership and proposal:** CAP-05 remains the canonical official source/relation-proof and applicability admission owner; its task names a refusal path and leaves the proposed capture→verified-relation producer unresolved, a CAP-05 disposition. CNT-04 supplies case-selected law/effectivity/competence/actual-act material, case data/config, and legal review; its write-scope does not authorize shared runtime writes. DES-05 owns the new engineering for generic multi-norm interpretation/branch composition in existing Lex semantic owners **and the consuming Scientist adapter**. It consumes CAP-05 relation evidence and CNT-04 case inputs; CNT-08 compares changed bases and CNT-09 proves the selected case/status/surface. DES-05 is implementation plus consumer integration, not coordination only; no duplicate legal service or shared-source writes by CNT-04.

Branches retain source spans/version, supporting and contrary provisions, exception/cross-reference/delegation alternatives, time/jurisdiction/language assumptions, unresolved targets, and disagreement. Unknown authority limits authority-bearing use but permits exploratory design and proposed amendments. **Bounded residual:** the inspected paths do not establish the complete synthesis/artifact/consumer chain. Accepted-source census assigns producer_missing/artifact_missing/bridge_missing only where it actually finds the missing link; this review allocates their investigation/repair and semantic proof, not a global absence claim.

**Falsifier:** two provisions plus cross-reference, exception, and two lawful as-of versions yield competing branches; material change affects only dependent designs/comparison. Remove the exception edge but keep “checked” markers; Scientist loses/limits the affected branch. Current-law claims still require CAP-05 admission.

### R14-F06 — Substantive candidate document projection (DES-06)

**Evidence/coverage:** `scientist/policy_design/output.py@dccea950845cda5b38f026e7770c07819d31f4d9:130-199,557-596` has PolicyBrief and PolicyArtifactBundle. `core/contracts/runtime.py@dccea950845cda5b38f026e7770c07819d31f4d9:113-143,1844-1927` and `runtime/http/services/bureaucratic_rendering.py@dccea950845cda5b38f026e7770c07819d31f4d9:66-142` supply a versioned AST and renderer; routes resolve an exact manifest view. CNT-09 is the selected-case surface host; UI-02 owns publication.

**Bounded gap/proposal:** extend those owners to render useful options, draft provisions, explanation, impact, implementation, and monitoring from the exact candidate bundle. Bind material text/table cells to claim/provision/metric, version, status, unit/denominator, period, uncertainty, audience, and purpose. Profiles are extensible presentation grammar, not a policy template catalogue. Proposed provisions remain not enacted/in force absent an admitted act. **Labels:** `verification_missing`, `semantic_test_missing` for claim/quantity fidelity; existing render producer/surface exist. Public raw candidate prose is `surface_out_of_scope` absent a permitted projection.

**Falsifier:** remove a material source binding or alter a unit while retaining document IDs/watermark; content check and fresh CNT-09 consumer must limit or reject the statement. Test reader comprehension and source fidelity, not section count.

### R14-F07 — Human edit to candidate delta and recomputation (DES-07)

**Evidence/coverage:** `apps/runtime-dashboard/src/features/artifacts/bureaucratic/BureaucraticArtifactView.tsx@dccea950845cda5b38f026e7770c07819d31f4d9` is read-only. The pinned exporter is `apps/runtime-dashboard/src/features/artifacts/bureaucratic/export/export-docx.ts@dccea950845cda5b38f026e7770c07819d31f4d9`; its “DOCX” source packet is HTML-backed, not evidence of editable DOCX round-trip. No inspected task owns edit→semantic delta→re-evaluation.

**Bounded gap/proposal:** extend the same document revision owner and canonical Scientist/orchestration path, not a CMS or second source of policy truth. Persist immutable revisions; map stable AST IDs; keep ambiguous text/value as unbound candidate; route policy-relevant edits as typed patches to recomputation. Rewritten claims lose old support until resolved; proposed text never mutates current law. **Labels:** `surface_missing` for authorized edit/import, `bridge_missing`, `verification_missing`, `semantic_test_missing`. Rendering/read surfaces are present.

**Falsifier:** strengthen a cited claim and change a table quantity in a real editable carrier. Old citation cannot automatically support the new claim; quantity must alter the fresh evaluation or remain unbound. Removing dispatch while retaining endpoint names/hashes fails.

### R14-F08 — Balanced cross-run experience in PDC search (DES-08)

**Evidence/coverage:** `scientist/methods/search/lessons.py@dccea950845cda5b38f026e7770c07819d31f4d9` and `scientist/orchestration/memory/retrieval.py@dccea950845cda5b38f026e7770c07819d31f4d9` provide scoped CAS lessons and balanced retrieval; transfer/Pareto seeds exist. PDC stores rejected lessons but inspected `policy_design/search.py@dccea950845cda5b38f026e7770c07819d31f4d9:1002-1036` does not retrieve them into later proposals. The formulator’s default `InMemoryHypothesisLedger` makes persistence conditional on an injected sink (`scientist/policy_design/formulator.py@dccea950845cda5b38f026e7770c07819d31f4d9:413-450`). LIF-07 owns lineage, CNT-08 ancestry/dependence, GYD-25 retrieval, not transfer utility.

**Bounded gap/proposal:** extend the canonical Scientist memory/search consumer. Reuse outcome-backed success, refutation, and unexecuted records with scope, preconditions, versions, exposure/selection, cost, provenance, and revocation. Prior LLM hypotheses remain candidate refs; they do not become evidence. Keep separate from O1/O2/O3, posterior updates, and world writes. **Labels:** `bridge_missing` / `implemented_but_not_orchestrated` for PDC retrieval; conditional `artifact_missing` for default sink without persistence injection; `semantic_test_missing` for transfer.

**Falsifier:** frozen source-disjoint memory-on/off comparison at matched budgets, with stale, shifted, poisoned-success, and contaminated cases. Removing retrieval returns baseline; missing evaluator provenance excludes success; no memory can update world state.

### R14-F09 — LLM invocation, context, and replay provenance (DES-09)

**Evidence/coverage:** N4 and Scientist candidate/prompt-tool ledgers already carry parts of prompt, tool, repair, and input lineage; G6 already bounds its tool route. The F03 false-assistance label proves client availability is not invocation. CAP/LIF/OPS own rights, lineage, resources, and egress controls.

**Bounded gap/proposal:** join existing records for actual call, provider/model/version (or explicit unknown), prompt/tools/context refs, result, budget/spend, failure/degradation, and replay class. Preserve contrary material or record typed context loss. Add no gateway, budget ledger, or hidden chain-of-thought store. Unknown provider determinism supports trace reconstruction, not exact replay. G6 public no-recommendation-text and tool admission stay unchanged. **Labels:** `verification_missing`, `semantic_test_missing` for invocation/context truth; public raw candidate text is `surface_out_of_scope`.

**Falsifier:** provider configured but call suppressed cannot claim LLM authorship; omitted exception with “complete” marker must expose loss; dropping provenance while retaining candidate labels cannot promote or execute the proposal.

### R14-F10 — Independent productive-capability evaluation (DES-10)

**Evidence/coverage:** GYD-17/18/19/20/21/22 cover loop, distributions, firewall, replay, validation, and health; GYD-25 retrieval; GYD-26 judge binding; CNT-09/UI-02 the case surface. Missing allocation is a selection-resistant comparison of non-paraphrase alternatives and document comprehension, not a generator or safety subsystem.

**Bounded gap/proposal:** extend GYD-18/22 and the native benchmark owner with frozen no-op, grammar, safe LLM, hybrid, and memory-off arms under matched maximum budgets. Report actual costs and a vector of feasibility/robustness, semantic diversity, fidelity, false abstention, comprehension, and disagreement. Reuse GYD-20/25/26; add no judge/benchmark registry. Quality is diagnostic; `useful_design_rate` is not a promotion target. **Labels:** `verification_missing`, `semantic_test_missing` for productive quality.

**Falsifier:** paraphrases preserving count/recall/front markers reduce measured option coverage; replacing all output with no-op yields zero incremental support; omitted cases/arms/holdout queries make the denominator check fail or the result `not_established`.

## Full-chain acceptance, sources, and open boundaries

After E02 acceptance/rebind, one commissioned case must show: request plus declared unknowns → native N4 mechanisms → persisted candidate/provenance → N6 feedback and joint evaluation → selected legal branches, when relevant → Scientist comparison → candidate document → human edit as candidate delta → native recomputation → fresh CNT-08/CNT-09 status, audit, and permitted surface. A known allowed case must produce substantive alternatives; unknowns must yield a bounded frontier, limitation, and next step. All participants bind exact artifacts/versions. Document/interface design can proceed before E02; product code, fixtures executed through product paths and runtime implementation wait for actual E02 acceptance. Within that admitted execution, isolated preparation may precede supplier completion; no fixture establishes composed acceptance.

**Primary research and limits.** [FunSearch (Nature 2024)](https://www.nature.com/articles/s41586-023-06924-6) and [AlphaEvolve (2025)](https://arxiv.org/abs/2506.13131) pair LLM proposals with explicit evaluators and lineage; math/code score does not prove policy effect, law, or value. [MAP-Elites](https://arxiv.org/abs/1504.04909) supports retaining diverse high-quality candidates, but chosen descriptors have blind spots; N6 is the nearer owner. [LLAMBO (ICLR 2024)](https://proceedings.iclr.cc/paper_files/paper/2024/file/84b8d9fcb4e262fcd429544697e1e720-Paper-Conference.pdf) supports an LLM proposal channel for data-sparse optimization; HPO is not causal policy validation. [Reflexion](https://arxiv.org/abs/2303.11366) motivates outcome-conditioned experience; [adaptive holdout research](https://arxiv.org/abs/1506.02629) warns repeated feedback can leak. Reflection is not evidence, and a checksum is not a holdout guarantee. OASIS [LegalRuleML](https://docs.oasis-open.org/legalruleml/legalruleml-core-spec/v1.0/os/legalruleml-core-spec-v1.0-os.html) / [Akoma Ntoso](https://docs.oasis-open.org/legaldocml/akn-core/v1.0/os/part1-vocabulary/akn-core-v1.0-os-part1-vocabulary.html) inform structure, not interpretation/authority; [COLIEE 2024](https://coliee.org/archive/coliee-2024) separates retrieval from entailment on bounded legal tasks. HM Treasury’s [Green Book 2026](https://www.gov.uk/government/publications/the-green-book--2/the-green-book-2026) informs appraisal, not universal templates/values.

**Open, not ratified:** semantic-equivalence criteria without closing universal grammar; principal-approved task and reader rubric/sample size without a universal best-policy score; which legal relations are computable versus institutionally supplied; authorized document carrier/audience; provider/context limits; and case-specific limits of candidate-memory use under the existing no-authority/no-active-LLM-influence rules. These are execution-profile/oracle inputs, not blanket new architecture approvals; the preferred native paths are specified in DES cards. SDD edits require their normal owner/principal review; this audit does not resolve them or widen GYD-23.

**Pattern pass:** P01/P02/P03, P04/P05/P09/P15, P07/P08, P10/P14, P11, P13/P27/P30/P31, P25, P29/P32/P33, P35–P38. Concrete anti-pattern: `hybrid_seed_llm_assisted` can be selected by client presence without invocation. Target: native owners, candidate-only unknown-preserving generation, real behavior checks, independently examined quality, and persisted effects at a fresh consumer. No global runtime-absence claim is made.
