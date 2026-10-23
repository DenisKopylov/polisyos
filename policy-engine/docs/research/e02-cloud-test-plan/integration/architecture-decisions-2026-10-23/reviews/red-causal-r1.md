# Red-team R1 — PAG candidate transport and legal-relation boundary

Review target: `03-pag-scope-and-legal-relation.md` and `04-conditional-transport-diagnostic.md` in `policy-engine/docs/research/e02-cloud-test-plan/integration/architecture-decisions-2026-10-23/`.

Evidence pin: F12 question packet/source commit `f12fb9895a4009ce77828554f4c5c18d83e6ec15`; workspace brief says doc/research only, `code_acceptance=false`, `closure_ids=[]`. The original PAG/R4 question is already open. This review did not run tests or change product files. Historical `7 PASS / 1 FAIL` is an author-reported replay over manual SCM inputs, not evidence of a legal-positive path, source-trained graph, PAG completion correctness, or B33/B214 closure.

## Decision

Keep the useful candidate outcome as a real design target, but do not activate the existing sampler or call it a validated PAG sensitivity analysis. The source shows both (a) a correct current refusal for direct PAG/CPDAG scalar solving and (b) a legacy sampling routine that erases endpoint/latent semantics. The minimum viable positive is a **registered, finite, validated completion profile** (or a PAG-native method for an explicitly exact domain) inserted at the candidate graph-method dispatch stage. It can report sensitivity over its selected finite family without claiming that the family covers every PAG completion. Keep the protected scalar refusal and Lex authority refusal intact.

This avoids both errors in the drafts’ tension: “heuristic orientation sensitivity” does not make an unsound generator safe, while the defects in the current generator do not justify making all candidate PAG computation permanently unsupported.

## Blockers and minimal structural repairs

### B1 — Current sampled orientations are not validated PAG completions

**Bucket:** existing B214 / P10 class, one level deeper at the generator; do not count each edge-mark escape as a new finding. P31/P40 call for a class-level generator repair.

At F12 `policy-engine/src/polisyos/foundry/methods/catalog/causal/transport_check.py:483-555`, `_sample_dag_candidates_from_pag` proposes binary directions, rejects only duplicate signatures and DAG cycles, and silently drops those proposals. `_orientation_options_from_pag_edge` preserves tail-arrow / arrow-tail edges, but maps every other endpoint pair to one or two directed edges and `_oriented_edge` rewrites the marks to tail-arrow. Thus circle endpoints lose their ancestral/equivalence constraints. An arrow-arrow (bidirected/confounding) edge, if admitted by this model, is turned into a directed edge; it is not a harmless direction choice. Acyclicity is necessary for a DAG, not a proof that the graph is a consistent extension/member of the PAG’s represented class. The routine also does not establish maximality/ancestral constraints or membership in the PAG equivalence class. Its baseline plus seeded proposals are neither exhaustive nor a justified uniform sample.

The exact F12 `GraphType` in `policy-engine/src/polisyos/ir/analytics/causal_graph.py:40-48` is `DAG`, `CPDAG`, `PAG`, `MGRAPH`, `ADMG`. There is no `MAG` enum here; `MGRAPH` is PolicyOS’s missingness graph with `R_X`/`X_star`, not a MAG. Correct Draft03’s “MAG” list and do not route MGRAPH as MAG. Edge marks are tail/arrow/circle at lines 58-64. If the source representation cannot express or validate a required completion, return profile-specific unsupported; do not approximate away its semantics.

**Minimal repair:** register a completion profile at the existing graph/method owner boundary. It must (1) bind the input PAG bytes/profile and graph semantics; (2) produce a finite, named set of candidate members while preserving compelled marks and latent/selection meaning; (3) validate every emitted member against the source partial graph and the selected completion semantics, not just acyclicity; and (4) give each accepted member an identity/ref and the generator/validator/profile revision. Then run the existing DAG/ADMG transport method only on each validated resolved member. Alternatively, use an existing/new PAG-native transport method only for its declared exact domain. Do not demand a proof that the finite set is all compatible completions: label the result “sensitivity over selected validated family,” expose the selection/generation policy and limits, and make no whole-PAG completeness or probability claim. If the profile is not requested/supported or yields no valid members, return a truthful typed candidate disposition. No change to direct scalar PAG/CPDAG admission.

The PAG identification literature is inspiration for method-owner work, not proof that this transport solver implements it: [Jaber et al. (ICML 2019)](https://proceedings.mlr.press/v97/jaber19a.html) and [Jaber et al. (NeurIPS 2022)](https://proceedings.neurips.cc/paper_files/paper/2022/hash/17a9ab4190289f0e1504bbb98d1d111a-Abstract-Conference.html) address identification under PAG/Markov-equivalence assumptions; [Bareinboim and Pearl (AAAI)](https://ojs.aaai.org/index.php/AAAI/article/view/8232) concerns transportability under specified source/target assumptions. None licenses a random-DAG approximation as a validated transport method.

### B2 — The supposed current solver route is unreachable for PAG, and the legacy sampler has two gates

**Bucket:** P01/P02 `bridge_missing` / `implemented_but_not_orchestrated`, deeper at the requested candidate method. This is not a reason to weaken the current gate.

F12 `transport_engine.py:64-104, 641-667` calls `scalar_graph_admission_refusal` before downstream solving; PAG and CPDAG return `partial_graph_completion_semantics_not_established`. F12 `transport_check.py:263-305` invokes that same refusal before reaching the `PAGIdentificationPolicy.PROBABILISTIC` branch. Therefore the old sampler cannot currently produce the requested positive through either shown entry path. Merely splitting Lex’s refusal from graph refusal still leaves the graph refusal in place. Calling the current all-in-one PAG sampler “conditional candidate” does not address this.

**Minimal repair:** make a requested candidate profile explicit in the existing method dispatch after actual graph/profile/query/context binding and before the scalar graph gate. That candidate-only branch invokes the registered finite completion generator/validator, then the existing scalar solver on each admitted completed DAG/ADMG. The public/direct scalar PAG path continues to refuse. The selected outer result remains `UNSUPPORTED/NONE/false`; candidate results stay nested and cannot set scalar formula/confidence/readiness. Retire or route the legacy sampler so no alternate call path can still turn its sample fraction into top-level `IDENTIFIED`. State the exact trigger (registered candidate profile/request in the existing workflow contract); “if requested” without a request discriminator or call-site is not a bridge. If no real orchestration path is selected, diagnose `bridge_missing`, not a successful contract.

### B3 — Lex relation verification is an authority refusal, not resource-access authorization

**Bucket:** same P05 authority-boundary class already selected; the plane conflation is a deeper instance, not a new legal subsystem requirement.

F12 `policy-engine/src/polisyos/data_forge/domains/legal/source_relation.py:1-7, 17-23, 61-68` defines only `verification_missing` and `require_legal_source_relation_verification()` always raises. F12 `lex/legal_evaluation/transport_constraints.py:113-126` calls it before constraint lookup and explicitly says there is no independent claim-to-source verifier. There is no positive relation producer/receipt here. Draft03’s instruction to “reuse ... the existing producer/consumer chain” overstates the available chain, and “implement ... positive intake/source-bound verification bridge now where the law is known” risks implying an established source/issuer or positive producer that the packet explicitly lacks.

This Lex gate addresses whether a legal SPO claim may be relied on as authority. It does not establish permission to read, process, or disclose a dataset. Conversely, missing legal claim verification does not prove data access is denied. Candidate math may run on authorized or synthetic inputs while policy-level claim relation is declared unknown; an applicable resource/tenant/privacy/license denial still blocks the actual read/compute/disclosure. Draft03 should name the actual existing access owner/predicate and where it is checked before materialization and at output/cache reads. If that owner cannot be identified in this decision, record the bridge/input as unresolved rather than implying a generic “access owner” already gates it.

**Minimal repair:** preserve the exact Lex outer refusal until a genuine independently verified relation receipt and accountable producer exist. Do not introduce a legal-positive producer from architecture prose or LLM output. Separately require the real data/resource owner’s operation-specific access admission for candidate work. Treat unknown legal relation as a declared candidate limitation, never as permission, absence of prohibition, or a reason to bypass access. Positive candidate tests may use permitted synthetic/manual graph inputs without waiting for legal-positive evidence.

### B4 — Execution accounting conflates proposal generation and solver evaluation

**Bucket:** P35/P38 denominator/proxy class, deeper at the two-stage execution path.

F12 sampler lines 501-540 tries a baseline and up to `max(sample_cap*60, 200)` random proposals, stops after enough unique acyclic candidates, and silently drops duplicate/cyclic proposals. Draft04’s single counting unit cannot tell a reader how much graph-generation work was attempted versus how many validated completions reached the solver. A ratio over only successful solver returns would also hide rejected proposals, invalid members, solver errors, and truncated work. The old `id_confidence`/threshold changes top-level identification and confidence (lines 385-447), so it cannot be copied into the nested field under a new label and preserve semantics.

**Minimal repair:** record two linked ledgers: (a) completion-generation budget/proposals, baseline, duplicate, invalid/rejected with reason, unique validated members, unattempted budget and termination; (b) solver attempts over validated member IDs, completed/failed/not-run, and termination. Bind seed, proposal distribution/policy, cap, validator and solver versions. If reporting a fraction, name its exact denominator (e.g. successfully evaluated validated members) and keep failures/truncation visible; zero denominator has no ratio. Call it descriptive sensitivity over the selected family, never calibrated confidence/posterior probability or an identification bound. If threshold logic is retained for search prioritization, it cannot set even the nested candidate’s authority status and never the outer result.

### B5 — Version tuple and old-reader behavior remain owner inputs, not established compatibility

**Bucket:** existing IR-Q2/P07 compatibility question; not a new decision, but do not let selected version labels close it.

F12 packet `README.md`, `Q2-version-compatibility.md`, and `required-inputs.md` say supported producer versions, historical aliases/artifacts and migration semantics are owner inputs; question-specific runtime probes are UNRUN. Draft04 selects result payload/manifest `2.2` and report `1.1`, but its “known owner-established 1.0/2.0/2.1” language should be conditional until the source owner establishes each exact tuple. The prior reported tuple mismatch (result DTO default 2.1 vs CAS manifest 1.0 vs registry 1.0/2.0) is not solved by accepting a list of version strings.

**Minimal repair:** before new writes, produce one explicit compatibility matrix keyed by the complete tuple: payload schema, CAS schema name/version, kind/media, DTO contract/ref identity, migration transform, and owner-established payload semantics. Unknown/mismatched tuples fail typed admission; do not use version alone, silently restamp old bytes, or drop the nested field for old readers while claiming a lossless round trip. Upgrade all required readers first. Reconcile the 33-path seed inventory with current direct and indirect consumers; it is not a cap. Name any externally supported reader/client cohort or explicitly bound the claim to a complete, evidenced in-tree cohort. Maintain an explicit old-writer/no-diagnostic mode only if a real old representation is owner-supported and report its omitted capability.

The nested result must preserve exact outer refusal and be unable to improve protected readiness/ranking. Old scalar readers are especially risky: no new top-level mirrors; old historical scalar values retain their provenance and are not reinterpreted. A projection that omits a candidate diagnostic must disclose the omission and cannot advertise lossless full-result semantics.

### B6 — Late relation evidence must update current evaluation without rewriting event history

**Bucket:** existing B161 / P07-P08 time and lifecycle class, deeper at legal relation admission.

Draft03’s append-only receipt and as-known-at distinction are directionally correct. Tighten the re-evaluation key: the later receipt must be independently verified and same source/claim/graph/query/jurisdiction/scope, with its valid/effective interval and receipt/admission time kept distinct. It may change today’s relation assessment only for the scope/time it actually covers. It cannot backdate admission, rewrite the historical refused result, authorize unrelated source reads, or convert a cached candidate into an authority claim. Recheck current operation access separately; legal relation and data access remain distinct predicates.

**Minimal repair:** create a new verification/admission receipt and current result/claim generation through the existing custody owner; retain the historical refusal and original replay. Apply normal invalidation/revalidation to claims whose validity changes. Do not invent a broader late-evidence refinement rule beyond the same-scope owner law.

## Useful positive, preserved

The design should accept this case: a user asks for a declared PAG candidate sensitivity profile over a named manual or otherwise grounded graph; the actual input operation is allowed (or the input is synthetic); a registered finite completion profile yields a few validated graph members; existing DAG/ADMG transport owner evaluates them; result/report are persisted and freshly consumed; output explains that sensitivity is only over those selected members; Lex’s protected legal relation remains unknown and outer status remains exactly `UNSUPPORTED/NONE/false`. This is useful conditional math without policy-claim authority.

It should also preserve direct PAG scalar refusal, unknown or denied data-resource access refusal, and refusal when the named profile/generator cannot validate a member. Avoid both blanket refusal for all candidate PAG work and blanket acceptance of arbitrary acyclic orientations. The draft’s strong outer boundary is right; its current legacy sampler is not a valid positive implementation.

## Acceptance falsifiers to add to the spec (not run here)

- A topology/mark control where only a compelled direction or latent/confounding relation changes must either change/reject the completion family correctly; same node names cannot pass. Include circle-circle, circle-arrow, tail-arrow, and bidirected/latent cases if supported by the type. Verify every emitted member and prove that removing the validator while retaining labels makes the positive fail.
- A positive candidate route traverses the actual registered request, validated completion owner, existing resolved-graph solver, result persistence, report persistence, fresh GET/consumer. Assert exact outer refusal before/after and no scalar mirror. Removing solver/property must make positive fail.
- Proposal accounting cases: baseline only; duplicate-only proposals; cycle/semantic-invalid proposals; validated candidates with solver failure; truncation at generation and solver budgets; zero accepted and zero evaluated. Show generation and evaluation totals reconcile separately.
- Access denied before materialization and revocation before output/cache read; this is distinct from missing Lex source relation. Synthetic authorized candidate succeeds under legal unknown while protected authority remains refused.
- Exact old-version tuple controls only after owner establishment, unknown well-formed version, mismatched manifest/payload, old reader against new writer, and any projection that would drop nested diagnostics. Do not treat a guessed predecessor as a positive control.
- Same-scope genuine late receipt updates current assessment but not historic bytes/as-known-at replay; wrong-scope or backdated receipt cannot change it.

## Pattern buckets

- P05: legal authority vs operation access vs candidate computation; same selected authority class, decomposed by plane.
- P10/P31/P40 (B214): partial-graph semantics destroyed by binary orientation projection; same known graph-meaning class, close with one registered generator/validator contract.
- P01/P02: scalar PAG refusal remains correct but candidate call path/positive producer bridge is missing; authorize actual extension at method dispatch.
- P35/P38: generation proposals and solver evaluations are distinct denominators; one ratio is a proxy for actual work.
- P07/P08/B161: exact version/time/evidence lifecycle remains owner-bound; no version or late event self-authenticates.
- P29/P32/P37: tests must exercise actual graph membership, resolve-bind-verify, and authority property, not field markers or declared assumptions.
